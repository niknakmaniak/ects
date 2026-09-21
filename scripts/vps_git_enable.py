"""Active GIT_AUTO_PUSH sur le VPS sans ecraser les autres secrets."""

import os
import sys

import paramiko

HOST = os.environ.get("VPS_HOST", "148.113.242.154")
USER = os.environ.get("VPS_USER", "ubuntu")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ECTS_DIR = "/opt/ects"
GIT_TOKEN = os.environ.get("GIT_GITHUB_TOKEN", "")


def run(client, cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    print(f"$ {cmd[:100]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-3000:])
    if err.strip() and code != 0:
        print("ERR:", err.strip()[-1500:])
    return code, out, err


def patch_env(text: str) -> str:
    lines = text.splitlines()
    keys = {
        "GIT_AUTO_PUSH": "true",
        "GIT_REMOTE_URL": "https://github.com/niknakmaniak/ects.git",
        "GIT_USER_NAME": "ECTS Bot",
        "GIT_USER_EMAIL": "ects@bot.local",
    }
    if GIT_TOKEN:
        keys["GIT_GITHUB_TOKEN"] = GIT_TOKEN

    present = {line.split("=", 1)[0]: i for i, line in enumerate(lines) if "=" in line and not line.strip().startswith("#")}
    for key, val in keys.items():
        entry = f"{key}={val}"
        if key in present:
            lines[present[key]] = entry
        else:
            lines.append(entry)
    return "\n".join(lines) + "\n"


def main():
    if not PASSWORD:
        print("Set VPS_PASSWORD", file=sys.stderr)
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=20)

    sftp = client.open_sftp()
    with sftp.file(f"{ECTS_DIR}/.env", "r") as f:
        env_text = f.read().decode()
    new_env = patch_env(env_text)
    with sftp.file(f"{ECTS_DIR}/.env", "w") as f:
        f.write(new_env)
    sftp.close()

    run(client, f"chmod 600 {ECTS_DIR}/.env")
    run(client, f"cd {ECTS_DIR} && git pull --ff-only")
    run(client, f"cd {ECTS_DIR} && git config --global --add safe.directory {ECTS_DIR}")
    run(client, f"cd {ECTS_DIR} && git config user.name 'ECTS Bot' && git config user.email 'ects@bot.local'")

    if GIT_TOKEN:
        run(
            client,
            f"cd {ECTS_DIR} && git ls-remote origin HEAD >/dev/null 2>&1 && echo GIT_AUTH_OK || echo GIT_AUTH_FAIL",
        )
    else:
        print("WARN: GIT_GITHUB_TOKEN absent — push auto actif mais push echouera sans PAT GitHub.")

    run(client, f"cd {ECTS_DIR}/infra && docker compose up -d --build", timeout=900)
    run(client, "curl -sf http://127.0.0.1:8080/health || echo HEALTH_FAIL")
    client.close()
    print("\n=== GIT AUTO PUSH CONFIGURE ===")


if __name__ == "__main__":
    main()
