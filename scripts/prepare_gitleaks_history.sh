#!/usr/bin/env bash
# Materialize and verify the selected history without printing file contents.
set -Eeuo pipefail
set +x
umask 077

case "${1:-}" in
  ref-history) scope=HEAD ;;
  all-refs) scope=--all ;;
  *) echo 'Expected ref-history or all-refs' >&2; exit 2 ;;
esac
test -n "${RUNNER_TEMP:?}"
test -n "${GH_TOKEN:?}"

# Partial clones can need a late authenticated fetch after checkout has
# deliberately removed its credentials. Keep this header in this process's
# environment only; never persist it in the caller's repository or argv.
index=${GIT_CONFIG_COUNT:-0}
[[ "$index" =~ ^[0-9]+$ ]]
authorization="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
export "GIT_CONFIG_KEY_${index}=http.https://github.com/.extraheader"
export "GIT_CONFIG_VALUE_${index}=$authorization"
export GIT_CONFIG_COUNT=$((index + 1))

objects=$(mktemp "$RUNNER_TEMP/gitleaks-history-objects.XXXXXXXX")
inventory=$(mktemp "$RUNNER_TEMP/gitleaks-history-inventory.XXXXXXXX")
trap 'rm -f -- "$objects" "$inventory"' EXIT
git rev-list --objects --no-object-names "$scope" > "$objects"
git cat-file --batch-check='%(objectname) %(objecttype)' < "$objects" > "$inventory"
if grep -q ' missing$' "$inventory"; then
  echo 'Cannot scan the selected history: Git objects are unavailable' >&2
  exit 1
fi
echo 'Selected Git history objects are available for Gitleaks'
