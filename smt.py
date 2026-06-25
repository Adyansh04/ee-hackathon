#!/usr/bin/env python3
"""Fetch a Unitree Go2 AES key without printing it.

This helper writes the hex-encoded key to an ignored local file. Do not commit
the output file, paste it into chat, or bake it into a Docker image.
"""

from __future__ import annotations

import argparse
import binascii
from getpass import getpass
from pathlib import Path
import stat

import paramiko


DEFAULT_OUTPUT = Path("apps/dimos-go2-tester/.secrets/unitree_aes_key")
DEFAULT_REMOTE_KEY = "/unitree/etc/key/aes_key.bin"


def read_key(host: str, users: list[str], password: str, remote_path: str) -> bytes:
    last_error: Exception | None = None

    for user in users:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, username=user, password=password, timeout=5)
            try:
                sftp = client.open_sftp()
                try:
                    with sftp.open(remote_path, "rb") as remote_file:
                        return remote_file.read()
                finally:
                    sftp.close()
            except Exception:
                _stdin, stdout, stderr = client.exec_command(f"cat {remote_path}")
                data = stdout.read()
                if data:
                    return data
                err = stderr.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(err or f"no data returned for {remote_path}")
        except Exception as exc:
            last_error = exc
        finally:
            client.close()

    raise RuntimeError(f"failed to fetch key from {host}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.123.161")
    parser.add_argument("--user", action="append", dest="users", default=["root", "unitree"])
    parser.add_argument("--password", help="SSH password. If omitted, prompt securely.")
    parser.add_argument("--remote-path", default=DEFAULT_REMOTE_KEY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    password = args.password if args.password is not None else getpass("Unitree SSH password: ")
    key_bytes = read_key(args.host, args.users, password, args.remote_path)
    key_hex = binascii.hexlify(key_bytes).decode("ascii")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(key_hex + "\n", encoding="utf-8")
    args.output.chmod(stat.S_IRUSR | stat.S_IWUSR)

    print(f"Wrote Unitree AES key to {args.output}")
    print("Do not commit or print this file. Copy it to /data/dimos/unitree_aes_key on WendyOS.")


if __name__ == "__main__":
    main()
