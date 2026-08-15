#!/usr/bin/env bash
# Export the GitHub Dependency Graph repository SBOM as SPDX JSON.
#
# Usage:
#   scripts/export_repo_sbom.sh <owner/repo> [output-file]
#
# Requires `gh` authenticated with read access. The script never prints tokens;
# gh uses its credential store internally.
set -euo pipefail

repo="${1:-}"
output="${2:-sbom.spdx.json}"

if [ -z "$repo" ]; then
  echo "usage: $0 <owner/repo> [output-file]" >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh (GitHub CLI) is required: https://cli.github.com" >&2
  exit 3
fi

case "$repo" in
  */*) ;;
  *)
    echo "repo must be in owner/name form: $repo" >&2
    exit 4
    ;;
esac

mkdir -p "$(dirname "$output")"
gh api "repos/${repo}/dependency-graph/sbom" --jq '.sbom' > "$output"
python3 - "$output" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
doc = json.loads(path.read_text(encoding="utf-8"))
if doc.get("spdxVersion") != "SPDX-2.3":
    raise SystemExit(f"{path}: expected SPDX-2.3 sbom")
print(f"wrote {path}")
PY
