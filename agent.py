"""Windows branch agent v1. Standard library only; no remote shell or file ingestion."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import platform
import ssl
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

VERSION='1'

class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]

def protect(data,encrypt=True):
    if os.name!='nt':raise ValueError('Esta distribución protege credenciales con DPAPI de Windows.')
    buf=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte)));target=Blob()
    if encrypt:ok=ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:ok=ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    if not ok:raise ValueError('No se pudo proteger o leer el estado local.')
    try:return ctypes.string_at(target.data,target.size)
    finally:ctypes.windll.kernel32.LocalFree(target.data)

def metrics(allow_compute=False):
    result={'os':platform.system() if platform.system() in ['Windows','Linux','Darwin'] else 'Other','python':platform.python_version(),'model_ready':False,'memory_percent':None}
    if os.name=='nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(name,ctypes.c_ulonglong) for name in ['total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','avail_extended']]
        m=Memory();m.length=ctypes.sizeof(m)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):result['memory_percent']=m.load
    if allow_compute:
        try:
            opener=build_opener(ProxyHandler({}))
            with opener.open('http://127.0.0.1:11434/api/tags',timeout=3) as r:result['model_ready']=bool(json.load(r).get('models'))
        except Exception:pass
    return result

class API:
    def __init__(self,url,credential='',allow_local_http=False):
        parts=urlsplit(url)
        if parts.username or parts.password or parts.query or parts.fragment or parts.path not in ['', '/']:raise ValueError('Usa la dirección base del gateway, sin credenciales, rutas ni parámetros.')
        local=parts.scheme=='http' and parts.hostname in ['127.0.0.1','localhost'] and allow_local_http
        if not (parts.scheme=='https' and parts.hostname) and not local:raise ValueError('La sede debe usar HTTPS válido. HTTP solo está permitido para una prueba local explícita.')
        self.url=url.rstrip('/');self.credential=credential
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()))
    def __call__(self,path,body=None):
        data=json.dumps(body or {}).encode()
        req=Request(self.url+'/agent-api/v1'+path,data=data,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+self.credential} if self.credential else {})},method='POST')
        with self.opener.open(req,timeout=35) as response:return json.load(response)

class Worker:
    def __init__(self,api,allow_compute=False,allowed_models=None):
        self.api=api;self.allow_compute=allow_compute;self.allowed_models=allowed_models or ['qwen3:8b']
    def execute(self,job):
        kind=job['kind']
        if kind=='echo':return 'Conexión y ejecución de prueba correctas. Sin inferencia de IA.'
        if kind=='inventory':return json.dumps(metrics(self.allow_compute),ensure_ascii=False)
        if kind!='generate':raise ValueError('Tipo de trabajo no permitido.')
        if not self.allow_compute:raise ValueError('La inferencia local está desactivada en este equipo.')
        model=job['profile']['model']
        if model not in self.allowed_models:raise ValueError('Modelo no autorizado en la configuración local del equipo.')
        opener=build_opener(ProxyHandler({}))
        data={'model':model,'think':False,'stream':False,'keep_alive':0,
              'messages':[{'role':'system','content':'Eres '+job['profile']['name']+'. Entrega texto útil en español. No tienes herramientas para ejecutar código, leer archivos ni realizar acciones externas. Distingue propuesta de ejecución.'},{'role':'user','content':job['prompt']}],
              'options':{'num_ctx':4096,'num_predict':1200,'temperature':.2}}
        req=Request('http://127.0.0.1:11434/api/chat',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=240) as response:result=json.load(response)
        if result.get('done_reason')=='length':raise ValueError('La salida del modelo se truncó; requiere revisión.')
        text=result.get('message',{}).get('content','').strip()
        if not text:raise ValueError('El modelo no entregó contenido.')
        return text[:18000]
    def run_job(self,job):
        try:return {'lease':job['lease'],'ok':True,'result':self.execute(job),'error':''}
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else 'No se pudo ejecutar el trabajo local. Comprueba Ollama o la conectividad.'
            return {'lease':job['lease'],'ok':False,'result':'','error':message[:800]}

def save_json(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(path)

def run(config_path,once=False):
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    if 'credential_protected' not in config:raise ValueError('Falta la credencial protegida; ejecuta install.ps1.')
    credential=protect(bytes.fromhex(config['credential_protected']),False).decode()
    api=API(config['central_url'],credential if config.get('enrolled') else '',config.get('allow_local_http',False))
    if not config.get('enrolled'):
        enrolled=api('/enroll',{'key':credential,'label':config['label'],'version':VERSION})
        config['credential_protected']=protect(enrolled['token'].encode()).hex();config['enrolled']=True;config['node_id']=enrolled['node_id']
        save_json(config_path,config);api.credential=enrolled['token'];print('Equipo vinculado a la corporación.',flush=True)
    worker=Worker(api,config.get('allow_compute',False),config.get('allowed_models',['qwen3:8b']))
    spool=config_path.with_name('pending-result.dpapi')
    while True:
        success=True
        try:
            heartbeat=api('/heartbeat',metrics(worker.allow_compute))
            if spool.exists():
                pending=json.loads(protect(spool.read_bytes(),False).decode())
                try:api('/jobs/'+str(pending['job_id'])+'/result',pending['body']);spool.unlink()
                except HTTPError as exc:
                    if exc.code==409:
                        spool.replace(spool.with_name('undelivered-'+str(time.time_ns())+'.dpapi'))
                        print('Resultado fuera de plazo conservado cifrado para revisión.',flush=True)
                    else:raise
            if not spool.exists():
                leased=api('/lease')
                if leased.get('job'):
                    job=leased['job'];body=worker.run_job(job)
                    temp=spool.with_suffix('.tmp');temp.write_bytes(protect(json.dumps({'job_id':job['id'],'body':body}).encode()));temp.replace(spool)
                    api('/jobs/'+str(job['id'])+'/result',body);spool.unlink()
                    print('Trabajo R-'+str(job['id'])+' reportado: '+('DONE' if body['ok'] else 'ERROR'),flush=True)
                else:print('Equipo conectado; corporación '+heartbeat['corporation_status']+'. Sin trabajo.',flush=True)
        except HTTPError as exc:
            success=False
            print('La sede rechazó la operación: HTTP '+str(exc.code),flush=True)
            if exc.code in [401,403]:raise SystemExit('Credencial revocada o no válida. Requiere intervención del propietario.') from None
        except Exception:
            success=False
            print('Sede temporalmente no disponible; se conserva el resultado pendiente.',flush=True)
        if once:
            if not success:raise SystemExit(2)
            return
        time.sleep(max(15,min(300,int(config.get('poll_seconds',30)))))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    try:run(args.config.resolve(),args.once)
    except KeyboardInterrupt:pass
    except Exception:
        print('No se pudo iniciar el agente. Revisa el archivo de configuración y el gateway; no se han mostrado credenciales.',file=sys.stderr)
        sys.exit(1)
