import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
cmds = [
    "cd /opt/ects && git pull --ff-only",
    "cd /opt/ects/infra && docker compose up -d --build",
    "sleep 3 && curl -sf http://127.0.0.1:8080/health",
    "docker logs infra-ects-api-1 --tail 15 2>&1",
    "grep ECTS_API_TOKEN /opt/ects/.env | cut -d= -f1",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=300)
    print("===", cmd[:70])
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
# Print tokens for user (from .env)
_, o, _ = c.exec_command("grep -E '^(ECTS_API_TOKEN|ECTS_GPU_WORKER_TOKEN)=' /opt/ects/.env")
print("=== TOKENS (save these) ===")
print(o.read().decode())
c.close()
