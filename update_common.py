"""Release validation and filesystem operations shared by the local updater."""
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import stat
import uuid
import zipfile

BOOTSTRAP_PROTOCOL=1
MAX_PACKAGE=2_000_000
FILES=('agent.py','request_gui.py','permissions_gui.py','setup_gui.py','install.ps1','diagnose.ps1',
       'update_common.py','update_supervisor.py','update_setup.py',
       'Conectar-sucursal.cmd','Iniciar-agente.cmd','Solicitar-ayuda.cmd','Permisos-equipo.cmd','Activar-actualizaciones.cmd','Detener-agente.cmd',
       'README.md','AVISOS.md','SEDE_CENTRAL.md','APAGADO_TELEGRAM.md','CONTROL_DE_SUCURSALES.md','ACTUALIZACIONES.md','.gitignore','release-info.json')
URL=re.compile(r'^https://raw\.githubusercontent\.com/christian810/ai-corporation-agent/[0-9a-f]{40}/updates/agent-([0-9]+\.[0-9]+\.[0-9]+)\.zip$')

def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}',value):raise ValueError('Versión no válida.')
    return tuple(map(int,value.split('.')))

def validate_release(value):
    version(value['version'])
    match=URL.fullmatch(value['url'])
    if not match or match[1]!=value['version']:raise ValueError('Origen de actualización no autorizado o no fijado a un commit.')
    if value.get('bootstrap_protocol')!=BOOTSTRAP_PROTOCOL:raise ValueError('Esta actualización requiere otro instalador base.')
    if not re.fullmatch(r'[0-9a-f]{64}',value['sha256']):raise ValueError('Huella no válida.')
    if type(value['size']) is not int or not 0<value['size']<=MAX_PACKAGE:raise ValueError('Tamaño no permitido.')
    return value

def save(path,value):
    temporary=path.with_name(path.name+'.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(path)

def stage_package(base,release,content):
    validate_release(release)
    if len(content)!=release['size'] or hashlib.sha256(content).hexdigest()!=release['sha256']:raise ValueError('El paquete no coincide con la huella aprobada por la sede.')
    versions=(base/'versions').resolve();versions.mkdir(parents=True,exist_ok=True)
    target=versions/release['version']
    if target.exists():raise ValueError('La carpeta de esta versión ya existe; no se sobrescribe.')
    staging=versions/('.staging-'+uuid.uuid4().hex);staging.mkdir()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries=archive.infolist();seen=set();total=0
            if len(entries)>len(FILES):raise ValueError('Demasiados archivos en el paquete.')
            for entry in entries:
                name=entry.filename
                if name not in FILES or name.casefold() in seen or entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('El paquete contiene rutas, archivos o enlaces no permitidos.')
                seen.add(name.casefold());total+=entry.file_size
                if total>MAX_PACKAGE or entry.file_size>MAX_PACKAGE:raise ValueError('Paquete descomprimido demasiado grande.')
                data=archive.read(entry)
                if name.endswith('.py'):compile(data.decode('utf-8-sig'),name,'exec')
                (staging/name).write_bytes(data)
            if not {'agent.py','release-info.json'}.issubset(seen):raise ValueError('Faltan archivos del agente.')
        info=json.loads((staging/'release-info.json').read_text(encoding='utf-8-sig'))
        if info.get('version')!=release['version'] or info.get('bootstrap_protocol')!=BOOTSTRAP_PROTOCOL:raise ValueError('La versión interna no coincide.')
        staging.replace(target)
        return target
    finally:
        # Only remove the exact staging directory created above, inside the known versions directory.
        if staging.exists() and staging.resolve().parent==versions and staging.name.startswith('.staging-'):
            shutil.rmtree(staging)

class FileLock:
    def __init__(self,path):self.path=path;self.file=None
    def __enter__(self):
        import msvcrt
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b');self.file.seek(0,2)
        if not self.file.tell():self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:self.file.close();self.file=None;raise ValueError('Ya hay otro agente o actualizador abierto para este usuario de Windows.') from None
        return self
    def __exit__(self,*args):
        if self.file:
            import msvcrt
            self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1);self.file.close();self.file=None
