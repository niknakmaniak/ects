import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
cmds = [
    "grep FOLDER /opt/course-ai/.env 2>/dev/null || true",
    "grep INTAKE /opt/course-ai/.env 2>/dev/null || true",
    "grep FINISHED /opt/course-ai/.env 2>/dev/null || true",
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd, timeout=60)
    print("===", cmd)
    print(o.read().decode(errors="replace")[:2500])
c.close()
