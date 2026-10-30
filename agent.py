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
import threading
import subprocess
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

VERSION='1'
RELEASE_VERSION='1.1.0'

def agent_version():
    try:
        value=json.loads(Path(__file__).with_name('release-info.json').read_text(encoding='utf-8-sig'))['version']
        import re
        if re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}',value):return value
    except Exception:pass
    return RELEASE_VERSION

def heartbeat_payload(allow_compute=False,allow_shutdown=False,directory=None):
    status='MANUAL';enabled=False
    if directory:
        try:status=json.loads((directory/'update-status.json').read_text(encoding='utf-8'))['state']
        except Exception:pass
        try:enabled=json.loads((directory/'config.json').read_text(encoding='utf-8-sig')).get('auto_update') is True
        except Exception:pass
    return metrics(allow_compute)|{'heartbeat_seconds':5,'allow_shutdown':allow_shutdown,
                                 'agent_version':agent_version(),'update_status':str(status)[:40],'auto_update':enabled}

def desktop_notice(text):
    if os.name!='nt':raise ValueError('El aviso en pantalla requiere Windows.')
    message=text.strip()[:500] or 'Hola EmpresaX. Mensaje enviado desde la sede central.'
    show=ctypes.windll.user32.MessageBoxTimeoutW
    show.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.UINT,wintypes.WORD,wintypes.DWORD]
    show.restype=ctypes.c_int
    result=show(None,message,'AI Corporation · Sede central',0x00010040,0,20000)
    if result==0:raise ValueError('Windows no pudo mostrar el aviso en la sesión del agente.')
    return 'Aviso mostrado en la sesión Windows del agente; '+('cerrado automáticamente a los 20 segundos.' if result==32000 else 'cerrado por el usuario.')

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
    def __init__(self,url,credential='',allow_local_http=False,timeout=35):
        parts=urlsplit(url)
        if parts.username or parts.password or parts.query or parts.fragment or parts.path not in ['', '/']:raise ValueError('Usa la dirección base del gateway, sin credenciales, rutas ni parámetros.')
        local=parts.scheme=='http' and parts.hostname in ['127.0.0.1','localhost'] and allow_local_http
        if not (parts.scheme=='https' and parts.hostname) and not local:raise ValueError('La sede debe usar HTTPS válido. HTTP solo está permitido para una prueba local explícita.')
        self.url=url.rstrip('/');self.credential=credential;self.timeout=timeout
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()))
    def __call__(self,path,body=None):
        data=json.dumps(body or {}).encode()
        req=Request(self.url+'/agent-api/v1'+path,data=data,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+self.credential} if self.credential else {})},method='POST')
        with self.opener.open(req,timeout=self.timeout) as response:return json.load(response)

def shutdown_windows():
    if os.name!='nt':raise ValueError('El apagado requiere Windows.')
    executable=str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'/'shutdown.exe')
    completed=subprocess.run([executable,'/s','/t','0'],shell=False,capture_output=True,timeout=10,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if completed.returncode:raise ValueError('Windows no aceptó el apagado. Comprueba los permisos del usuario.')

def commit_shutdown(api,job,config_path):
    marker=config_path.with_name('power-consumed.json')
    consumed=json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else []
    if job['id'] in consumed:raise ValueError('La orden de apagado ya se consumió; no se repite.')
    api('/jobs/'+str(job['id'])+'/power-commit',{'lease':job['lease']})
    try:
        # Record before asking Windows. Interrupted power actions are never replayed.
        save_json(marker,(consumed+[job['id']])[-200:])
        shutdown_windows()
    except Exception:
        try:api('/jobs/'+str(job['id'])+'/power-failed',{'lease':job['lease']})
        except Exception:pass
        raise

class HeartbeatPump:
    """Independent of long model calls and Windows notices; no shared HTTP opener."""
    def __init__(self,api,allow_local_http=False,allow_compute=False,allow_shutdown=False,update_directory=None):
        self.api=API(api.url,api.credential,allow_local_http,timeout=4)
        self.stop=threading.Event();self.revoked=threading.Event();self.allow_compute=allow_compute;self.allow_shutdown=allow_shutdown
        self.update_directory=update_directory
    def loop(self):
        while not self.stop.is_set():
            started=time.monotonic()
            try:self.api('/heartbeat',heartbeat_payload(self.allow_compute,self.allow_shutdown,self.update_directory))
            except HTTPError as exc:
                if exc.code in [401,403]:self.revoked.set();return
            except Exception:pass
            self.stop.wait(max(.1,5-(time.monotonic()-started)))
    def __enter__(self):
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.thread.join(timeout=5)

class Worker:
    def __init__(self,api,allow_compute=False,allowed_models=None,allow_shutdown=False):
        self.api=api;self.allow_compute=allow_compute;self.allowed_models=allowed_models or ['qwen3:8b'];self.allow_shutdown=allow_shutdown
    def execute(self,job):
        kind=job['kind']
        if kind=='echo':return 'Conexión y ejecución de prueba correctas. Sin inferencia de IA.'
        if kind=='desktop_notice':return desktop_notice(job.get('prompt',''))
        if kind=='inventory':return json.dumps(metrics(self.allow_compute),ensure_ascii=False)
        if kind=='shutdown':
            if not self.allow_shutdown:raise ValueError('El apagado remoto está deshabilitado en este equipo.')
            return 'Orden de apagado recibida. Pendiente de autorización final y solicitud a Windows; no confirma apagado físico.'
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

def run(config_path,once=False,ready_file=None):
    from update_common import FileLock
    with FileLock(config_path.parent/'worker.lock'):_run(config_path,once,ready_file)

def _run(config_path,once=False,ready_file=None):
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    if 'credential_protected' not in config:raise ValueError('Falta la credencial protegida; ejecuta install.ps1.')
    credential=protect(bytes.fromhex(config['credential_protected']),False).decode()
    api=API(config['central_url'],credential if config.get('enrolled') else '',config.get('allow_local_http',False))
    if not config.get('enrolled'):
        enrolled=api('/enroll',{'key':credential,'label':config['label'],'version':VERSION})
        config['credential_protected']=protect(enrolled['token'].encode()).hex();config['enrolled']=True;config['node_id']=enrolled['node_id']
        save_json(config_path,config);api.credential=enrolled['token'];print('Equipo vinculado a la corporación.',flush=True)
    worker=Worker(api,config.get('allow_compute',False),config.get('allowed_models',['qwen3:8b']),config.get('allow_shutdown',False))
    spool=config_path.with_name('pending-result.dpapi')
    with HeartbeatPump(api,config.get('allow_local_http',False),worker.allow_compute,worker.allow_shutdown,config_path.parent) as pump:
        if ready_file:
            save_json(ready_file,{'version':agent_version(),'ready':True})
            permission=ready_file.with_suffix('.go')
            deadline=time.monotonic()+30
            while not permission.exists():
                if time.monotonic()>deadline:raise SystemExit(2)
                time.sleep(.1)
            permission.unlink(missing_ok=True)
        while True:
            if pump.revoked.is_set():
                print('Credencial revocada. Agente detenido.',flush=True);raise SystemExit(86)
            if (config_path.parent/'update-stop').exists() and not spool.exists():raise SystemExit(75)
            success=True
            try:
                heartbeat=api('/heartbeat',heartbeat_payload(worker.allow_compute,worker.allow_shutdown,config_path.parent))
                if spool.exists():
                    pending=json.loads(protect(spool.read_bytes(),False).decode())
                    try:api('/jobs/'+str(pending['job_id'])+'/result',pending['body']);spool.unlink()
                    except HTTPError as exc:
                        if exc.code==409:
                            spool.replace(spool.with_name('undelivered-'+str(time.time_ns())+'.dpapi'))
                            print('Resultado fuera de plazo conservado cifrado para revisión.',flush=True)
                        else:raise
                if (config_path.parent/'update-stop').exists() and not spool.exists():raise SystemExit(75)
                if not spool.exists():
                    leased=api('/lease')
                    if leased.get('job'):
                        job=leased['job'];body=worker.run_job(job)
                        temp=spool.with_suffix('.tmp');temp.write_bytes(protect(json.dumps({'job_id':job['id'],'body':body}).encode()));temp.replace(spool)
                        api('/jobs/'+str(job['id'])+'/result',body);spool.unlink()
                        print('Trabajo R-'+str(job['id'])+' reportado: '+('DONE' if body['ok'] else 'ERROR'),flush=True)
                        if job['kind']=='shutdown' and body['ok']:commit_shutdown(api,job,config_path)
                    else:print('Equipo conectado; corporación '+heartbeat['corporation_status']+'. Sin trabajo.',flush=True)
            except HTTPError as exc:
                success=False
                print('La sede rechazó la operación: HTTP '+str(exc.code),flush=True)
                if exc.code in [401,403]:
                    print('Credencial revocada o no válida. Requiere intervención del propietario.',flush=True);raise SystemExit(86) from None
            except Exception:
                success=False
                print('Sede temporalmente no disponible; se conserva el resultado pendiente.',flush=True)
            if once:
                if not success:raise SystemExit(2)
                return
            time.sleep(max(15,min(300,int(config.get('poll_seconds',30)))))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);parser.add_argument('--once',action='store_true');parser.add_argument('--ready-file',type=Path)
    args=parser.parse_args()
    try:run(args.config.resolve(),args.once,args.ready_file)
    except KeyboardInterrupt:pass
    except Exception:
        print('No se pudo iniciar el agente. Revisa el archivo de configuración y el gateway; no se han mostrado credenciales.',file=sys.stderr)
        sys.exit(1)
