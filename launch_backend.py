import subprocess
import time


OUT = r"C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\backend_out.log"
ERR = r"C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\backend_err.log"

with open(OUT, "wb") as out, open(ERR, "wb") as err:
    proc = subprocess.Popen(
        [r"D:\python\python.exe", "main.py"],
        cwd=r"C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\backend",
        stdout=out,
        stderr=err,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )

print("launched pid", proc.pid)
time.sleep(8)
print("poll after 8s:", proc.poll())
