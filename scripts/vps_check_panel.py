import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
_, o, _ = c.exec_command("curl -sf -o /dev/null -w 'login:%{http_code}' http://127.0.0.1:8080/login; echo; grep ECTS_PANEL /opt/ects/.env; docker ps --format '{{.Names}} {{.Status}}' | grep ects")
print(o.read().decode(errors="replace"))
c.close()
