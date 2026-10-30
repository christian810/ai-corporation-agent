"""One-time local enrollment into automatic updates; preserves existing branch policy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from update_common import FILES,FileLock,save,version
from agent import agent_version

def install(source,base):
    base.mkdir(parents=True,exist_ok=True)
    config_path=base/'config.json'
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    if not config.get('enrolled'):raise ValueError('Primero vincula el equipo. No se solicitará otra clave.')
    with FileLock(base/'supervisor.lock'),FileLock(base/'worker.lock'):
        state_path=base/'update-state.json'
        if not state_path.exists():
            initial=agent_version();version(initial)
            seed=base/'versions'/initial;seed.mkdir(parents=True,exist_ok=True)
            for name in FILES:
                if (source/name).is_file():shutil.copy2(source/name,seed/name)
            save(seed/'release-info.json',{'version':initial,'bootstrap_protocol':1})
            save(state_path,{'active':initial,'previous':None,'blocked':[]})
        for name in ['agent.py','update_common.py','update_supervisor.py','update_setup.py']:
            if (source/name).resolve()!=(base/name).resolve():shutil.copy2(source/name,base/name)
        # Only the update opt-in changes. DPAPI credential and execution permissions stay intact.
        config['auto_update']=True;save(config_path,config)

def register_startup(base):
    # Fixed task, current user and no elevation. Pythonw prevents a console on logon.
    executable=Path(sys.executable).with_name('pythonw.exe')
    if not executable.exists():executable=Path(sys.executable)
    def ps(value):return "'"+str(value).replace("'","''")+"'"
    arguments='"'+str(base/'update_supervisor.py')+'"'
    script="$ErrorActionPreference='Stop'\n"
    script+=f'$action=New-ScheduledTaskAction -Execute {ps(executable)} -Argument {ps(arguments)}\n'
    script+="$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name\n"
    script+="$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user\n"
    script+="$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited\n"
    script+="Register-ScheduledTask -TaskName 'AI Corporation Branch Agent' -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null\n"
    path=base/'register-startup.ps1';path.write_text(script,encoding='utf-8-sig')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(path)],capture_output=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Las actualizaciones se instalaron, pero Windows no permitió configurar el inicio de sesión automático. Puedes usar Iniciar-agente.cmd.')

def main():
    root=tk.Tk();root.title('Actualizaciones automáticas del agente');root.geometry('610x350')
    base=Path(os.environ['LOCALAPPDATA'])/'AI Corporation Agent';source=Path(__file__).resolve().parent
    tk.Label(root,text='Actualizar sin volver a descargar cada versión',font=('Segoe UI',13,'bold')).pack(pady=15)
    tk.Label(root,text='Cierra antes la ventana del agente anterior.\nSe conservarán la clave cifrada, los modelos y los permisos locales.\nSolo se ejecutarán paquetes de GitHub aprobados por tu sede.\nLas actualizaciones esperarán a que termine el trabajo en curso.',wraplength=560,justify='left').pack(padx=24,pady=10)
    startup=tk.BooleanVar(value=False)
    tk.Checkbutton(root,text='Iniciar el agente y el actualizador al entrar en Windows',variable=startup).pack(pady=10)
    def enable():
        try:
            install(source,base)
            if startup.get():register_startup(base)
            with (base/'updater.log').open('ab') as out:
                subprocess.Popen([sys.executable,str(base/'update_supervisor.py')],stdout=out,stderr=out,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except ValueError as exc:messagebox.showerror('No se completó la activación',str(exc));return
        except Exception:messagebox.showerror('No se completó la activación','Comprueba que este usuario ya tenga el equipo vinculado y que el agente anterior esté cerrado. No se muestran credenciales.');return
        messagebox.showinfo('Activado','Agente y actualizador iniciados en segundo plano. La sede mostrará su versión. Puedes cerrar esta ventana.');root.destroy()
    def disable():
        try:
            path=base/'config.json';config=json.loads(path.read_text(encoding='utf-8-sig'));config['auto_update']=False;save(path,config)
        except Exception:messagebox.showerror('Configuración','No se pudo leer o guardar la configuración local.');return
        messagebox.showinfo('Desactivado','No se buscarán nuevas versiones en la siguiente comprobación. El agente y su posible inicio de sesión automático siguen funcionando.');root.destroy()
    tk.Button(root,text='Instalar y activar actualizaciones',command=enable).pack(pady=10)
    tk.Button(root,text='Desactivar actualizaciones',command=disable).pack()
    root.mainloop()

if __name__=='__main__':main()
