#!/usr/bin/env python3
"""Transfer a file through an SSH gateway that only offers an interactive PTY.

No SCP, SFTP, rsync or invented TCP endpoint. Connection details stay CLI arguments.
The remote destination must be inside the explicitly named isolated project root.
"""

from __future__ import annotations
import argparse
import base64
import hashlib
import shlex
import subprocess
import textwrap
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--remote-name", required=True)
    args = parser.parse_args()
    name = PurePosixPath(args.remote_name)
    if name.is_absolute() or ".." in name.parts:
        raise ValueError("remote-name must be relative to the isolated project root")
    path = PurePosixPath(args.remote_root) / name
    payload = args.local.read_bytes()
    encoded = "\n".join(textwrap.wrap(base64.b64encode(payload).decode(), 76))
    expected = hashlib.sha256(payload).hexdigest()
    script = (
        "stty -echo\nPS1=''\nPS2=''\nbind 'set enable-bracketed-paste off'\n"
        + f"mkdir -p {shlex.quote(str(path.parent))}\n"
        + f"base64 -d > {shlex.quote(str(path))} <<'STAGE1_PAYLOAD_END'\n"
        + encoded
        + "\nSTAGE1_PAYLOAD_END\n"
        + f"printf '%s  %s\\n' {shlex.quote(expected)} {shlex.quote(str(path))} | sha256sum -c -\n"
        + "exit\n"
    )
    # -tt requests a remote PTY even when stdin is a pipe. The gateway may ignore
    # remote command arguments, so all shell commands are sent on stdin.
    result = subprocess.run(
        [
            "ssh",
            "-tt",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            "-i",
            str(args.identity.expanduser()),
            args.target,
        ],
        input=script,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if result.returncode or f"{path}: OK" not in result.stdout:
        raise RuntimeError("SSH transfer/checksum failed; inspect the gateway privately")
    print(f"Transferred {len(payload)} bytes; SHA-256 {expected}")


if __name__ == "__main__":
    main()
