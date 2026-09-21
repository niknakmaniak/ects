"""Configure Google Drive service account on VPS (secrets never committed)."""

import json
import os
import sys
import textwrap
from pathlib import Path

import paramiko

HOST = os.environ.get("VPS_HOST", "148.113.242.154")
USER = os.environ.get("VPS_USER", "ubuntu")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ECTS_DIR = "/opt/ects"
CRED_PATH_HOST = f"{ECTS_DIR}/credentials/google-service-account.json"
CRED_PATH_CONTAINER = "/repo/credentials/google-service-account.json"

# Optional overrides via env
INBOX_ID = os.environ.get("DRIVE_INBOX_FOLDER_ID", "")
PROCESSING_ID = os.environ.get("DRIVE_PROCESSING_FOLDER_ID", "")
FINISHED_ID = os.environ.get("DRIVE_FINISHED_FOLDER_ID", "")
ERROR_ID = os.environ.get("DRIVE_ERROR_FOLDER_ID", "")

SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")


def run(client, cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    print(f"$ {cmd[:100]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-2500:])
    if err.strip() and code != 0:
        print("ERR:", err.strip()[-1500:])
    return code, out, err


def patch_env(text: str) -> str:
    updates = {
        "GOOGLE_SERVICE_ACCOUNT_FILE": CRED_PATH_CONTAINER,
    }
    if INBOX_ID:
        updates["DRIVE_INBOX_FOLDER_ID"] = INBOX_ID
    if PROCESSING_ID:
        updates["DRIVE_PROCESSING_FOLDER_ID"] = PROCESSING_ID
    if FINISHED_ID:
        updates["DRIVE_FINISHED_FOLDER_ID"] = FINISHED_ID
    if ERROR_ID:
        updates["DRIVE_ERROR_FOLDER_ID"] = ERROR_ID

    lines = text.splitlines()
    present = {line.split("=", 1)[0]: i for i, line in enumerate(lines) if "=" in line and not line.strip().startswith("#")}
    for key, val in updates.items():
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
    sa_json = SERVICE_ACCOUNT_JSON
    if not sa_json:
        if SERVICE_ACCOUNT_FILE and os.path.isfile(SERVICE_ACCOUNT_FILE):
            sa_json = Path(SERVICE_ACCOUNT_FILE).read_text(encoding="utf-8")
        else:
            print("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE", file=sys.stderr)
            sys.exit(1)

    try:
        json.loads(sa_json)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=20)

    run(client, f"mkdir -p {ECTS_DIR}/credentials && chmod 700 {ECTS_DIR}/credentials")

    sftp = client.open_sftp()
    with sftp.file(CRED_PATH_HOST, "w") as f:
        f.write(sa_json if sa_json.endswith("\n") else sa_json + "\n")
    run(client, f"chmod 600 {CRED_PATH_HOST}")

    with sftp.file(f"{ECTS_DIR}/.env", "r") as f:
        env_text = f.read().decode()
    with sftp.file(f"{ECTS_DIR}/.env", "w") as f:
        f.write(patch_env(env_text))

    test_py = textwrap.dedent(
        """
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            '/repo/credentials/google-service-account.json',
            scopes=['https://www.googleapis.com/auth/drive'],
        )
        svc = build('drive', 'v3', credentials=creds)
        res = svc.files().list(pageSize=20, fields='files(id,name,mimeType)', q="trashed=false").execute()
        print('DRIVE_OK', len(res.get('files', [])))
        for f in res.get('files', [])[:10]:
            print(f['name'], f['id'], f['mimeType'])
        """
    ).strip()
    with sftp.file(f"{ECTS_DIR}/credentials/test_drive.py", "w") as f:
        f.write(test_py)
    sftp.close()

    run(client, f"chmod 600 {ECTS_DIR}/.env")
    run(client, f"cd {ECTS_DIR}/infra && docker compose up -d --build", timeout=900)
    run(client, "docker exec infra-ects-api-1 python /repo/credentials/test_drive.py", timeout=60)

    run(client, "curl -sf http://127.0.0.1:8080/health || echo HEALTH_FAIL")
    client.close()
    print("\n=== GOOGLE DRIVE CONFIGURE ===")
    if not INBOX_ID:
        print("WARN: DRIVE_INBOX_FOLDER_ID absent — partage le dossier inbox avec le service account puis relance avec DRIVE_INBOX_FOLDER_ID=...")


if __name__ == "__main__":
    main()
