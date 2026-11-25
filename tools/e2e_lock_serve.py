import subprocess, sys, time, glob, os
T=os.path.join(os.path.dirname(os.path.abspath(__file__)),"e2e_lock","out"); z=sorted(glob.glob(os.path.join(T,"*.zip")), key=os.path.getmtime)[-1]
for f in glob.glob(os.path.join(T,"*.apsave")): pass
srv=subprocess.Popen([r"C:\ProgramData\Archipelago\ArchipelagoServer.exe","--port","38281",z], stdin=subprocess.PIPE,
                     stdout=open(os.path.join(T,"srv.log"),"a"), stderr=subprocess.STDOUT, text=True)
cmd=os.path.join(T,"cmd.txt"); open(cmd,"w").close(); done=0
while srv.poll() is None:
    lines=open(cmd,encoding="utf-8").read().splitlines()
    for l in lines[done:]: srv.stdin.write(l+"\n"); srv.stdin.flush()
    done=len(lines); time.sleep(1)
