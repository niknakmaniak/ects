import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("148.113.242.154", username="ubuntu", password=os.environ["VPS_PASSWORD"], timeout=20)
_, o, _ = c.exec_command("docker logs infra-ects-api-1 --tail 40 2>&1")
print(o.read().decode(errors="replace"))
c.close()
