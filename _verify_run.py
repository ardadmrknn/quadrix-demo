import subprocess, signal

cmd = ["py", "main.py"]
p = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)

out = ""
timed_out = False
try:
    out, _ = p.communicate(timeout=8)
except subprocess.TimeoutExpired as e:
    timed_out = True
    out = e.output or ""
    try:
        p.send_signal(signal.CTRL_BREAK_EVENT)
        tail, _ = p.communicate(timeout=3)
        out += tail or ""
    except Exception:
        p.terminate()
        tail, _ = p.communicate(timeout=2)
        out += tail or ""

print(out)
print("[CHECK] TypeError float callable found:", "TypeError: 'float' object is not callable" in out)
print("[CHECK] Timed out after 8s:", timed_out)
print("[CHECK] Exit code:", p.returncode)
