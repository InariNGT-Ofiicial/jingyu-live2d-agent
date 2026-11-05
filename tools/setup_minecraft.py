"""Install official Java server and a private JRE into the disposable local test directory."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'.local/minecraft'
DEST.mkdir(parents=True,exist_ok=True)
def metadata(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Jingyu-local-setup'}),timeout=60) as r:return json.load(r)
def download(url,path,algorithm,digest):
    if path.exists() and hashlib.new(algorithm,path.read_bytes()).hexdigest()==digest:return
    with urllib.request.urlopen(url,timeout=120) as r,path.open('wb') as out:
        while chunk:=r.read(1024*1024):out.write(chunk)
    if hashlib.new(algorithm,path.read_bytes()).hexdigest()!=digest:raise ValueError('Download checksum mismatch: '+path.name)
    print('Downloaded and verified '+path.name,flush=True)
versions=metadata('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json')
version=metadata(next(v['url'] for v in versions['versions'] if v['id']=='1.20.1'))
server=version['downloads']['server'];download(server['url'],DEST/'server.jar','sha1',server['sha1'])
java=next(DEST.glob('jdk-*/bin/java.exe'),None)
if java is None:
    release=metadata('https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest')
    package=next(a for a in release['assets'] if a['name'].startswith('OpenJDK17U-jre_x64_windows_hotspot_') and a['name'].endswith('.zip'))
    checksum=next(a for a in release['assets'] if a['name']==package['name']+'.sha256.txt')
    with urllib.request.urlopen(checksum['browser_download_url'],timeout=60) as r:digest=r.read().decode().split()[0]
    archive=DEST/'jre.zip';download(package['browser_download_url'],archive,'sha256',digest)
    with zipfile.ZipFile(archive) as z:z.extractall(DEST)
    java=next(DEST.glob('jdk-*/bin/java.exe'))
world=DEST/'world-server';world.mkdir(exist_ok=True)
# This file applies only to the newly requested local test server.
(world/'eula.txt').write_text('eula=true\n',encoding='utf-8')
properties='''server-ip=127.0.0.1
server-port=25566
online-mode=false
enforce-secure-profile=false
level-name=jingyu-test
level-type=minecraft:flat
generate-structures=false
gamemode=survival
difficulty=peaceful
spawn-protection=0
view-distance=5
simulation-distance=5
max-players=3
max-tick-time=60000
motd=Jingyu local Minecraft experiment
enable-rcon=false
sync-chunk-writes=false
'''
if not (world/'server.properties').exists():(world/'server.properties').write_text(properties,encoding='utf-8')
(DEST/'runtime.json').write_text(json.dumps({'java':str(java),'jar':str(DEST/'server.jar'),'cwd':str(world),'version':'1.20.1','host':'127.0.0.1','port':25566},indent=2),encoding='utf-8')
print('Local Java 1.20.1 server ready to start',flush=True)
