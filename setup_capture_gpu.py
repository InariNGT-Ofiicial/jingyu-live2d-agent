"""Opt-in Windows per-application GPU preference for the capture interpreter."""
import argparse,json,sys
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description='Run with the capture Python. Choose the same GPU as VTS.');p.add_argument('--gpu',choices=['high-performance','power-saving','system'],required=True);a=p.parse_args()
    import winreg
    paths=sorted({str(Path(sys.executable).resolve()),str(Path(getattr(sys,'_base_executable',sys.executable)).resolve())})
    value={'high-performance':2,'power-saving':1,'system':0}[a.gpu]
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\DirectX\UserGpuPreferences') as key:
        for path in paths:winreg.SetValueEx(key,path,0,winreg.REG_SZ,f'GpuPreference={value};')
    print(json.dumps({'gpu':a.gpu,'interpreters':paths,'note':'Restart capture processes. The base interpreter preference also affects other scripts using it.'},ensure_ascii=True))
if __name__=='__main__':main()
