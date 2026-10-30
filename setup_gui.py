"""Interactive Windows enrollment. Never writes the bootstrap key to disk."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from urllib.error import HTTPError, URLError
from urllib.request import Request

from agent import API, VERSION, protect, save_json


def main():
    root = tk.Tk()
    root.title('Conectar sucursal a la sede')
    root.geometry('620x390')
    root.resizable(False, False)
    values = []
    for title, default, hidden in [
        ('Dirección HTTPS de la sede (gateway)', 'https://chris.tail91e028.ts.net:8443', False),
        ('Nombre del equipo', 'VM EmpresaX', False),
        ('Clave de alta nueva (válida durante 15 minutos)', '', True),
    ]:
        tk.Label(root, text=title, anchor='w').pack(fill='x', padx=24, pady=(12, 3))
        entry = tk.Entry(root, show='*' if hidden else '', font=('Segoe UI', 11))
        entry.insert(0, default)
        entry.pack(fill='x', padx=24)
        values.append(entry)
    status = tk.StringVar(value='La clave se cifra automáticamente. No necesitas editar ningún JSON.')
    tk.Label(root, textvariable=status, wraplength=570, justify='left').pack(padx=24, pady=12)
    install_root = Path(os.environ['LOCALAPPDATA']) / 'AI Corporation Agent'
    config_path = install_root / 'config.json'
    busy = False

    def finish(error=None):
        nonlocal busy
        busy = False
        button.config(state='normal')
        values[2].delete(0, 'end')
        if error:
            status.set(error)
            messagebox.showerror('No se ha conectado', error)
        else:
            status.set('Equipo vinculado. Agente iniciado en segundo plano. Ya puedes cerrar esta ventana.')
            messagebox.showinfo('Conexión correcta', 'La sede ha aceptado el equipo. Si la empresa está inactiva, actívala desde Corporaciones para enviar trabajos.')

    def connect():
        nonlocal busy
        if busy:
            return
        url, label, key = (entry.get().strip() for entry in values)
        if not label or len(label) > 120:
            messagebox.showerror('Nombre del equipo', 'Escribe un nombre de entre 1 y 120 caracteres.')
            return
        # Existing enrolled credentials are preserved; no key replacement or duplicate worker.
        if config_path.exists():
            try:
                old = json.loads(config_path.read_text(encoding='utf-8-sig'))
            except (ValueError, OSError):
                messagebox.showerror('Configuración existente', 'Hay un JSON ilegible. Conserva el archivo y solicita ayuda antes de sustituirlo.')
                return
            if old.get('enrolled'):
                messagebox.showinfo('Equipo ya instalado', 'Este usuario ya tiene un equipo dado de alta. No se ha sobrescrito ni iniciado otro agente. Comprueba su estado en la sede.')
                return
        if not key:
            messagebox.showerror('Falta la clave', 'Genera una clave nueva en Corporaciones y pégala en esta ventana.')
            return
        busy = True
        button.config(state='disabled')
        status.set('Comprobando HTTPS y dando de alta el equipo…')

        def work():
            enrolled = False
            try:
                api = API(url)
                with api.opener.open(Request(api.url + '/health'), timeout=15) as response:
                    health = json.load(response)
                if health.get('service') != 'corporation-agent-gateway' or health.get('protocol') != 1:
                    raise ValueError('Usa el gateway de agentes HTTPS del puerto 8443, no la dirección del panel.')
                # Check local permissions and DPAPI before consuming the one-time key.
                install_root.mkdir(parents=True, exist_ok=True)
                protect(b'local-check')
                source = Path(__file__).with_name('agent.py')
                target = install_root / 'agent.py'
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
                result = api('/enroll', {'key': key, 'label': label, 'version': VERSION})
                enrolled = True
                config = dict(central_url=api.url, label=label, enrolled=True,
                              node_id=result['node_id'], credential_protected=protect(result['token'].encode()).hex(),
                              allow_compute=False, allowed_models=['qwen3:8b'], poll_seconds=30)
                save_json(config_path, config)
                with (install_root / 'agent.log').open('ab') as out, (install_root / 'agent-error.log').open('ab') as err:
                    subprocess.Popen([sys.executable, str(target), '--config', str(config_path)],
                                     stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
            except HTTPError as exc:
                error = {401: 'La clave ha caducado, ya se usó o no es correcta. Genera una nueva en Corporaciones.',
                         403: 'La sede no permite el alta de esta corporación.',
                         404: 'La dirección no corresponde al gateway de agentes. Comprueba el puerto 8443.'}.get(exc.code, 'La sede respondió con HTTP ' + str(exc.code) + '.')
            except (URLError, TimeoutError):
                error = 'No se puede conectar por HTTPS. Comprueba Tailscale en la VM, la dirección y que la sede esté encendida.'
            except ValueError:
                error = 'La dirección o la respuesta del gateway no es válida. Usa una dirección HTTPS base, sin rutas.'
            except Exception:
                error = ('La sede aceptó el alta, pero falló el guardado o el inicio local. No repitas el alta: solicita ayuda para revisar el equipo en la sede.' if enrolled else
                         'No se pudo preparar la instalación local. Comprueba que Windows permite escribir en la carpeta del usuario.')
            else:
                error = None
            root.after(0, lambda: finish(error))
        threading.Thread(target=work, daemon=True).start()

    button = tk.Button(root, text='Conectar e iniciar agente', command=connect, font=('Segoe UI', 11))
    button.pack(pady=3)
    root.protocol('WM_DELETE_WINDOW', lambda: None if busy else root.destroy())
    root.mainloop()


if __name__ == '__main__':
    main()
