"""Local policy editor. Never shows credentials or requests elevation."""
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from agent import save_json

def main():
    root=tk.Tk();root.title('Permisos del equipo de sucursal');root.geometry('530x260')
    path=Path(os.environ['LOCALAPPDATA'])/'AI Corporation Agent'/'config.json'
    try:
        config=json.loads(path.read_text(encoding='utf-8-sig'))
        if not config.get('enrolled'):raise ValueError()
    except Exception:
        messagebox.showerror('Configuración','Primero vincula el equipo con el mismo usuario de Windows. No se ha modificado nada.');root.destroy();return
    tk.Label(root,text=config.get('label','Equipo de sucursal'),font=('Segoe UI',13,'bold')).pack(pady=15)
    enabled=tk.BooleanVar(value=bool(config.get('allow_shutdown',False)))
    tk.Checkbutton(root,text='Permitir apagado remoto confirmado desde Telegram',variable=enabled).pack(pady=8)
    tk.Label(root,text='Solo apaga este equipo. No permite shell ni instalaciones.\nGuarda el trabajo antes de confirmar un apagado.\nReinicia el agente después de cambiar este permiso.',wraplength=490).pack(pady=10)
    def save():
        if enabled.get() and not config.get('allow_shutdown'):
            if not messagebox.askyesno('Autorizar control de energía','¿Permites que el propietario de la sede solicite apagar este Windows tras confirmar el equipo en Telegram?',default='no'):return
        config['allow_shutdown']=enabled.get();save_json(path,config)
        messagebox.showinfo('Permiso guardado','Cierra el agente anterior y vuelve a abrir Iniciar-agente.cmd para aplicar el cambio. No hace falta otra clave.');root.destroy()
    tk.Button(root,text='Guardar permiso local',command=save).pack(pady=8)
    root.mainloop()

if __name__=='__main__':main()
