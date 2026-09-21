import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
cmds = [
    "grep -E '^(GIT_AUTO_PUSH|GIT_REMOTE_URL|GIT_USER_NAME)=' /opt/ects/.env",
    "grep '^GIT_GITHUB_TOKEN=' /opt/ects/.env | sed 's/=.*/=***/'",
    "docker exec infra-ects-api-1 python -c 'from app.config import get_settings; s=get_settings(); print(\"auto_push\", s.git_auto_push, \"token_set\", bool(s.git_github_token))'",
    "curl -sf http://127.0.0.1:8080/health",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    print("===", cmd[:70])
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
