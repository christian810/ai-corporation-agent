"""Small branch terminal: HQ performs inference; this computer only sends text."""
import json
import os
from pathlib import Path
import threading
import time
import uuid
import tkinter as tk
from tkinter import ttk,messagebox
from urllib.error import HTTPError
from agent import API,protect,save_json

def main():
    root=tk.Tk();root.title('EmpresaX · Solicitar ayuda a la sede');root.geometry('720x600')
    base=Path(os.environ['LOCALAPPDATA'])/'AI Corporation Agent'
    pending=base/'central-pending.json'
    tk.Label(root,text='Envía un encargo de texto a la IA central. No necesitas Ollama en este equipo.').pack(padx=15,pady=12)
    area=ttk.Combobox(root,values=['Soporte','Red e infraestructura','Contabilidad','Proyectos'],state='readonly');area.current(0);area.pack()
    prompt=tk.Text(root,height=6,wrap='word');prompt.pack(fill='x',padx=15,pady=10)
    prompt.insert('1.0','Propón tres comprobaciones sencillas para mejorar la red de una pequeña empresa. Solo recomendaciones, sin ejecutar cambios.')
    state=tk.StringVar(value='Preparado. La sede conserva el encargo y el resultado asociados a esta empresa.')
    tk.Label(root,textvariable=state,wraplength=680).pack(padx=15,pady=6)
    output=tk.Text(root,height=15,wrap='word',state='disabled');output.pack(fill='both',expand=True,padx=15,pady=10)
    busy=False
    def show(text):
        output.config(state='normal');output.delete('1.0','end');output.insert('1.0',text);output.config(state='disabled')
    def finish(text,error=False):
        nonlocal busy
        busy=False;send.config(state='normal');echo.config(state='normal')
        state.set('No se ha completado. Puedes reintentar la solicitud pendiente.' if error else 'Resultado recibido de la sede central.');show(text)
    def submit(kind):
        nonlocal busy
        if busy:return
        text=prompt.get('1.0','end').strip()
        if not 3<=len(text)<=6000:messagebox.showerror('Encargo','Escribe entre 3 y 6000 caracteres.');return
        payload={'client_id':uuid.uuid4().hex,'kind':kind,'area':['support','network','accounting','projects'][area.current()],'prompt':text}
        try:
            config=json.loads((base/'config.json').read_text(encoding='utf-8-sig'))
            if not config.get('enrolled'):raise ValueError()
            credential=protect(bytes.fromhex(config['credential_protected']),False).decode()
            api=API(config['central_url'],credential,timeout=10)
            if pending.exists():payload=json.loads(pending.read_text(encoding='utf-8'))
            else:save_json(pending,payload)
        except Exception:messagebox.showerror('Configuración','No se pudo leer la configuración cifrada. Usa el mismo usuario de Windows con el que vinculaste el equipo.');return
        busy=True;send.config(state='disabled');echo.config(state='disabled');state.set('Enviando solicitud a la sede…')
        def work():
            try:
                r=api('/requests',payload)
                rid=r['id'];root.after(0,lambda:state.set(f'Solicitud S-{rid}: esperando a la sede. Puedes seguir trabajando en este equipo.'))
                deadline=time.monotonic()+1200
                while r['status'] in ['QUEUED','WORKING'] and time.monotonic()<deadline:
                    time.sleep(2);r=api('/requests/'+str(rid))
                if r['status']=='DONE':
                    save_json(base/'central-last-result.json',r);pending.unlink(missing_ok=True)
                    result=f"S-{rid} · procesado por la sede · modelo: {r.get('model') if r['kind']=='text' else 'sin IA'}\n\n"+r['result']
                    root.after(0,lambda:finish(result))
                elif r['status']=='ERROR':
                    pending.unlink(missing_ok=True);message=r['error'];root.after(0,lambda:finish(message,True))
                else:root.after(0,lambda:finish('La solicitud sigue pendiente. Vuelve a pulsar para consultar la misma petición, sin duplicarla.',True))
            except HTTPError as exc:
                message={401:'La credencial está revocada o no es válida.',403:'El equipo no tiene autorización.',409:'La empresa no está activa.',429:'Se ha alcanzado el límite de solicitudes pendientes.'}.get(exc.code,'La sede respondió con HTTP '+str(exc.code))
                root.after(0,lambda:finish(message,True))
            except Exception:root.after(0,lambda:finish('No se puede contactar con la sede. Comprueba Tailscale y reintenta; se conserva la misma solicitud.',True))
        threading.Thread(target=work,daemon=True).start()
    controls=tk.Frame(root);controls.pack(pady=8)
    send=tk.Button(controls,text='Pedir ayuda a la IA central',command=lambda:submit('text'));send.pack(side='left',padx=8)
    echo=tk.Button(controls,text='Prueba de ida y vuelta sin IA',command=lambda:submit('echo'));echo.pack(side='left',padx=8)
    root.mainloop()

if __name__=='__main__':main()
