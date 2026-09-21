import os
import secrets
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)

panel_pass = os.environ.get("ECTS_PANEL_PASSWORD") or secrets.token_urlsafe(12)
panel_secret = secrets.token_hex(32)

cmds = [
    "cd /opt/ects && git pull --ff-only",
    f"grep -q '^ECTS_PANEL_USER=' /opt/ects/.env || echo 'ECTS_PANEL_USER=admin' >> /opt/ects/.env",
    f"grep -q '^ECTS_PANEL_SECRET=' /opt/ects/.env || echo 'ECTS_PANEL_SECRET={panel_secret}' >> /opt/ects/.env",
    "sed -i 's/^ECTS_PANEL_PASSWORD=.*/ECTS_PANEL_PASSWORD=" + panel_pass.replace("'", "'\\''") + "/' /opt/ects/.env || echo 'ECTS_PANEL_PASSWORD=" + panel_pass + "' >> /opt/ects/.env",
    "grep -q '^ECTS_PANEL_PASSWORD=' /opt/ects/.env || echo 'ECTS_PANEL_PASSWORD=" + panel_pass + "' >> /opt/ects/.env",
    "cd /opt/ects/infra && docker compose up -d --build",
    "sleep 3 && curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/login",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=300)
    print(o.read().decode(errors="replace"), end="")
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
print("PANEL_USER=admin")
print("PANEL_PASSWORD=" + panel_pass)
print("URL=http://148.113.242.154:8080/panel")
c.close()
