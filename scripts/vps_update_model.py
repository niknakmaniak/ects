import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
cmds = [
    "cd /opt/ects && git pull --ff-only",
    "grep LLM_MODEL /opt/ects/.env || true",
    "sed -i 's/^LLM_MODEL=.*/LLM_MODEL=kimi-k3/' /opt/ects/.env",
    "cd /opt/ects/infra && docker compose up -d --build",
    "sleep 4 && curl -sf http://127.0.0.1:8080/health",
    "ss -tlnp | grep 8080 || netstat -tlnp 2>/dev/null | grep 8080 || true",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=300)
    print("===", cmd[:70])
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
