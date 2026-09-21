"""Deploy ECTS on VPS via SSH. Usage: VPS_PASSWORD=... python scripts/deploy_vps.py"""

import os
import secrets
import sys
import textwrap

import paramiko

HOST = os.environ.get("VPS_HOST", "148.113.242.154")
USER = os.environ.get("VPS_USER", "ubuntu")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ECTS_DIR = "/opt/ects"
MOONSHOT_KEY = os.environ.get("MOONSHOT_API_KEY", "")


def run(client, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"$ {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-4000:] if len(out) > 4000 else out)
    if err.strip() and code != 0:
        print("ERR:", err[-2000:])
    return code, out, err


def main():
    if not PASSWORD:
        print("Set VPS_PASSWORD env var", file=sys.stderr)
        sys.exit(1)
    if not MOONSHOT_KEY:
        print("Set MOONSHOT_API_KEY env var", file=sys.stderr)
        sys.exit(1)

    api_token = secrets.token_hex(24)
    gpu_token = secrets.token_hex(24)
    panel_password = secrets.token_urlsafe(16)
    panel_secret = secrets.token_hex(32)

    env_content = textwrap.dedent(
        f"""
        ECTS_ENV=production
        ECTS_DATA_DIR=/data
        ECTS_REPO_ROOT=/repo
        DATABASE_URL=postgresql+psycopg://ects:ects@postgres:5432/ects
        ECTS_API_HOST=0.0.0.0
        ECTS_API_PORT=8080
        ECTS_API_TOKEN={api_token}
        ECTS_GPU_WORKER_TOKEN={gpu_token}
        ECTS_PANEL_USER=admin
        ECTS_PANEL_PASSWORD={panel_password}
        ECTS_PANEL_SECRET={panel_secret}
        ECTS_DEFAULT_DEADLINE_HOUR=8
        LLM_PROVIDER=moonshot
        LLM_BASE_URL=https://api.moonshot.cn/v1
        LLM_API_KEY={MOONSHOT_KEY}
        LLM_MODEL=kimi-k3
        LLM_MONTHLY_BUDGET_EUR=999
        GIT_REMOTE_URL=https://github.com/niknakmaniak/ects.git
        GIT_AUTO_PUSH=false
        WHISPER_MODEL=large-v3
        LORA_MIN_SESSIONS=3
        """
    ).strip()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=20)

    run(client, f"sudo mkdir -p {ECTS_DIR} && sudo chown {USER}:{USER} {ECTS_DIR}")
    code, out, _ = run(client, f"test -d {ECTS_DIR}/.git && echo HAS_GIT || echo NO_GIT")
    if "NO_GIT" in out:
        run(client, f"git clone https://github.com/niknakmaniak/ects.git {ECTS_DIR}")
    else:
        run(client, f"cd {ECTS_DIR} && git pull --ff-only")

    sftp = client.open_sftp()
    with sftp.file(f"{ECTS_DIR}/.env", "w") as f:
        f.write(env_content)
    sftp.close()
    run(client, f"chmod 600 {ECTS_DIR}/.env")

    code, _, _ = run(client, f"cd {ECTS_DIR}/infra && docker compose up -d --build", timeout=900)
    run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'ects|NAMES' || docker ps")
    run(client, "curl -sf http://127.0.0.1:8080/health || echo HEALTH_FAIL")

    client.close()
    print("\n=== DEPLOY OK ===")
    print(f"ECTS_API_TOKEN={api_token}")
    print(f"ECTS_GPU_WORKER_TOKEN={gpu_token}")
    print("UI: http://127.0.0.1:8080 (via SSH tunnel ou Tailscale)")
    print(f"Tokens saved in {ECTS_DIR}/.env on VPS")


if __name__ == "__main__":
    main()
