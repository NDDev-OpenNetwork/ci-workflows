#!/usr/bin/env bash
# Preserve complete redacted scanner outputs when GitHub artifact storage is unavailable.
set -euo pipefail
exec python3 -I - "$@" <<'PY'
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

LIMIT = 4 * 1024 * 1024
NAMES = (
    "private-security-actionlint.log", "private-security-zizmor.sarif",
    "private-security-osv.sarif", "private-security-gitleaks.sarif",
)

def main():
    identity = {
        "schema_version": 1,
        "repository": os.environ["GITHUB_REPOSITORY"],
        "source_commit": os.environ["GITHUB_SHA"],
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
    }
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", identity["repository"]):
        raise ValueError("invalid repository identity")
    if not re.fullmatch(r"[0-9a-f]{40}", identity["source_commit"]):
        raise ValueError("invalid source commit")
    if any(not re.fullmatch(r"[1-9][0-9]*", identity[key]) for key in ("run_id", "run_attempt")):
        raise ValueError("invalid run identity")
    root = Path(os.environ["RUNNER_TEMP"])
    if not root.is_absolute():
        raise ValueError("RUNNER_TEMP must be absolute")
    files = {}
    for name in NAMES:
        fd = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > LIMIT:
                raise ValueError("evidence must be a bounded regular file: " + name)
            raw = source.read(LIMIT + 1)
            after = os.fstat(source.fileno())
            key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if len(raw) > LIMIT or len(raw) != before.st_size or key(before) != key(after):
                raise ValueError("evidence changed while captured: " + name)
        if name.endswith(".sarif"):
            document = json.loads(raw)
            if document.get("version") != "2.1.0" or not isinstance(document.get("runs"), list):
                raise ValueError("invalid SARIF: " + name)
        files[name] = raw
    files["identity.json"] = (json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n").encode()
    files["SHA256SUMS"] = "".join(
        hashlib.sha256(raw).hexdigest() + "  " + name + "\n"
        for name, raw in sorted(files.items())
    ).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    # Base64 cannot form a workflow command. Emit only after every input was
    # captured and validated; no partial archive can be mistaken for evidence.
    print("SECURITY_EVIDENCE_V1_BEGIN " + digest + " " + str(len(raw)))
    print(base64.encodebytes(raw).decode(), end="")
    print("SECURITY_EVIDENCE_V1_END " + digest)
    print("::warning::Artifact upload failed; complete redacted security evidence is retained in this run log (SHA-256 " + digest + ").")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        fd = os.open(summary, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(fd, "a") as target:
            target.write("\n### Security evidence fallback\n\nArtifact storage was unavailable. The complete redacted ZIP is base64-encoded between `SECURITY_EVIDENCE_V1_BEGIN/END` in this step's log. SHA-256: `" + digest + "`. The ZIP includes all four reports, run identity, and `SHA256SUMS`. Scanner failures remain failures.\n")

try:
    main()
except (OSError, ValueError, KeyError) as error:
    print("security evidence fallback failed: " + str(error), file=sys.stderr)
    sys.exit(1)
PY
