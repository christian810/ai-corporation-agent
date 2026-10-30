"""Stable Windows bootstrap. Only HQ-approved immutable releases may run automatically."""
import argparse
import json
from pathlib import Path
import ssl
import subprocess
import sys
import time
import uuid
from urllib.request import build_opener,ProxyHandler,HTTPSHandler,HTTPRedirectHandler,Request
from agent import API,protect
from update_common import FileLock,MAX_PACKAGE,save,stage_package,validate_release,version

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('No se aceptan redirecciones del paquete de actualización.')

def download(release):
    validate_release(release)
    opener=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
    # No branch bearer credential is ever sent to GitHub.
    with opener.open(Request(release['url'],headers={'User-Agent':'AI-Corporation-Updater/1'}),timeout=25) as response:
        content=response.read(MAX_PACKAGE+1)
    if len(content)>MAX_PACKAGE:raise ValueError('Descarga demasiado grande.')
    return content

class Supervisor:
    def __init__(self,base,check_seconds=300):
        self.base=base.resolve();self.config_path=self.base/'config.json';self.child=None;self.child_log=None
        self.state_path=self.base/'update-state.json';self.stop_file=self.base/'update-stop'
        self.master_stop=self.base/'supervisor-stop'
        self.state=json.loads(self.state_path.read_text(encoding='utf-8'))
        version(self.state['active'])
        self.check_seconds=max(1,int(check_seconds))
    def config(self):return json.loads(self.config_path.read_text(encoding='utf-8-sig'))
    def status(self,status,**extra):
        save(self.base/'update-status.json',{'state':status,'active':self.state['active'],'previous':self.state.get('previous'),'updated_at':time.time(),**extra})
    def write_state(self):save(self.state_path,self.state)
    def api(self):
        config=self.config()
        if not config.get('enrolled'):raise ValueError('Primero vincula el equipo.')
        credential=protect(bytes.fromhex(config['credential_protected']),False).decode()
        return API(config['central_url'],credential,config.get('allow_local_http',False),timeout=10)
    def close_log(self):
        if self.child_log:self.child_log.close();self.child_log=None
    def start(self,release):
        version(release)
        self.stop_file.unlink(missing_ok=True)
        ready=self.base/('ready-'+uuid.uuid4().hex+'.json')
        self.close_log();log=self.base/'managed-agent.log'
        if log.exists() and log.stat().st_size>2_000_000:log.replace(self.base/'managed-agent.previous.log')
        self.child_log=log.open('ab')
        self.child=subprocess.Popen([sys.executable,str(self.base/'versions'/release/'agent.py'),'--config',str(self.config_path),'--ready-file',str(ready)],
                                    stdout=self.child_log,stderr=self.child_log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.started_at=time.monotonic()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if self.child.poll() is not None:self.close_log();return False
            if ready.exists():
                try:info=json.loads(ready.read_text(encoding='utf-8'))
                except (OSError,ValueError):info={}
                if info.get('version')==release:
                    ready.with_suffix('.go').write_text('Startup accepted; work may begin.',encoding='utf-8')
                    ready.unlink(missing_ok=True);return True
            time.sleep(.2)
        # Candidate never passed startup: it must not remain running beside the rollback.
        self.child.terminate();self.child.wait(timeout=10);self.close_log();return False
    def rollback(self,bad):
        previous=self.state.get('previous')
        if previous:version(previous)
        self.state['blocked']=list(set(self.state.get('blocked',[])+[bad]))[-50:]
        if previous and (self.base/'versions'/previous/'agent.py').exists():
            self.state['active']=previous;self.state['previous']=None;self.write_state()
            self.status('ROLLED_BACK',failed_version=bad)
            return self.start(previous)
        self.write_state();self.status('ERROR',failed_version=bad);return False
    def activate(self,candidate):
        old=self.state['active']
        self.status('TESTING',candidate=candidate)
        if not self.start(candidate):
            self.state['blocked']=list(set(self.state.get('blocked',[])+[candidate]))[-50:];self.write_state()
            self.status('ROLLED_BACK',failed_version=candidate)
            return self.start(old)
        self.state.update(active=candidate,previous=old);self.write_state();self.status('CURRENT')
        return True
    def wait_for_idle(self,candidate):
        self.status('WAITING_IDLE',candidate=candidate)
        self.stop_file.write_text('Restart at the next idle boundary. Never interrupt a running job.',encoding='utf-8')
        while self.child.poll() is None:time.sleep(.5)
        self.close_log()
        return self.child.returncode==75
    def run(self):
        self.master_stop.unlink(missing_ok=True)
        # If a prior supervisor crashed, ask its orphan worker to stop at an idle boundary.
        self.stop_file.write_text('Recover supervisor ownership at idle.',encoding='utf-8')
        deadline=time.monotonic()+360
        while True:
            try:
                with FileLock(self.base/'worker.lock'):pass
                break
            except ValueError:
                if time.monotonic()>deadline:raise ValueError('El agente anterior no ha terminado su trabajo; no se iniciará otro.')
                time.sleep(1)
        if not self.start(self.state['active']):
            if not self.rollback(self.state['active']):return
        next_check=0;waiting=None
        try:
            while True:
                if self.master_stop.exists():self.status('STOPPING');return
                if self.child.poll() is not None:
                    self.close_log()
                    if waiting and self.child.returncode==75:
                        self.activate(waiting);waiting=None
                    elif self.child.returncode==0:
                        self.status('STOPPED');return
                    elif self.child.returncode==86:
                        self.status('REVOKED');return
                    elif time.monotonic()-self.started_at<60 and self.state.get('previous'):
                        if not self.rollback(self.state['active']):return
                    else:
                        self.status('RESTARTING');time.sleep(10)
                        if not self.start(self.state['active']):return
                if time.monotonic()>=next_check and not waiting:
                    next_check=time.monotonic()+self.check_seconds
                    try:
                        if not self.config().get('auto_update',False):self.status('DISABLED')
                        else:
                            release=self.api()('/updates/manifest').get('release')
                            if release and version(release['version'])>version(self.state['active']) and release['version'] not in self.state.get('blocked',[]):
                                validate_release(release);self.status('DOWNLOADING',candidate=release['version'])
                                if not (self.base/'versions'/release['version']).exists():stage_package(self.base,release,download(release))
                                waiting=release['version']
                                if self.wait_for_idle(waiting) and not self.master_stop.exists():self.activate(waiting)
                                waiting=None
                            else:self.status('CURRENT')
                    except Exception:self.status('UPDATE_ERROR')
                time.sleep(1)
        finally:
            # A deliberate supervisor stop also asks the worker to stop after its current work.
            if self.child and self.child.poll() is None:self.stop_file.write_text('Stop at idle.',encoding='utf-8')
            deadline=time.monotonic()+360
            while self.child and self.child.poll() is None and time.monotonic()<deadline:time.sleep(.5)
            self.close_log()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--tool',choices=['request_gui.py','permissions_gui.py'])
    parser.add_argument('--stop',action='store_true')
    args=parser.parse_args();base=args.base.resolve()
    if args.stop:
        (base/'supervisor-stop').write_text('Stop supervisor and worker at idle.',encoding='utf-8');return
    if args.tool:
        state=json.loads((base/'update-state.json').read_text(encoding='utf-8'));version(state['active'])
        subprocess.Popen([sys.executable,str(base/'versions'/state['active']/args.tool)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return
    with FileLock(base/'supervisor.lock'):Supervisor(base).run()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except Exception:
        print('No se pudo iniciar el actualizador. Comprueba que no haya otro abierto y revisa la configuración local.',file=sys.stderr);sys.exit(1)
