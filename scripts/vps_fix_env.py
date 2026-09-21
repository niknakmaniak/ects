import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)

panel_pass = "iBsMRINVLMY5xVwp"  # already set on VPS

fix_env = r"""python3 << 'PY'
from pathlib import Path
p = Path("/opt/ects/.env")
text = p.read_text()
text = text.replace("LORA_MIN_SESSIONS=3ECTS_PANEL_USER=admin", "LORA_MIN_SESSIONS=3\nECTS_PANEL_USER=admin")
if "ECTS_PANEL_USER=" not in text:
    text += "\nECTS_PANEL_USER=admin\n"
if "ECTS_PANEL_PASSWORD=" not in text:
    text += f"ECTS_PANEL_PASSWORD={panel_pass}\n"
if "ECTS_PANEL_SECRET=" not in text:
    text += "ECTS_PANEL_SECRET=dd49bfa5c1272e39e3ad233fd6ae2a4331287da9301c405cf5c85a11e2a84ec1\n"
p.write_text(text)
print("fixed")
PY"""

cmds = [
    fix_env,
    "cd /opt/ects/infra && docker compose up -d --build",
    "sleep 5 && curl -sf -o /dev/null -w 'health:%{http_code} login:%{http_code}' http://127.0.0.1:8080/health http://127.0.0.1:8080/login",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=300)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
