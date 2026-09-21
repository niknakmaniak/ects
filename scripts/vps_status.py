import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
cmds = [
    "docker ps -a --format '{{.Names}} {{.Status}}'",
    "curl -sf http://127.0.0.1:8080/health || echo HEALTH_FAIL",
    "ls -la /opt/ects/",
    "cd /opt/ects/infra && docker compose ps 2>&1",
    "docker logs $(docker ps -q --filter name=ects-api) --tail 40 2>&1 || true",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=120)
    print("===", cmd[:70])
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
