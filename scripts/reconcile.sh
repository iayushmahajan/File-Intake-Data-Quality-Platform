#!/usr/bin/env bash
# Only the dedicated Reconcile Workbench runtime; no original-project fallback.
set -euo pipefail
REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
SETTINGS="$REPO/.env.reconcile.local"
compose() {
  env -i PATH="$PATH" HOME="$HOME" docker --context default compose \
    --env-file "$SETTINGS" --project-directory "$REPO" \
    -p reconcile-workbench -f "$REPO/compose.reconcile.yaml" "$@"
}
case "${1:-}" in
  init)
    python3 - "$SETTINGS" <<'PY'
import os, pathlib, secrets, stat, sys
path = pathlib.Path(sys.argv[1])
if path.exists():
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise SystemExit("Existing local settings must be a regular private 0600 file; nothing changed.")
    print("Private local settings already exist; preserved.")
else:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write('RECONCILE_DB_PASSWORD=' + secrets.token_hex(24) + '\n')
    print("Created private local settings; no provider credentials configured.")
PY
    ;;
  frontend)
    test -f "$REPO/frontend/node_modules/vite/bin/vite.js"
    cd "$REPO/frontend"
    exec env -i PATH="$PATH" HOME="$HOME" VITE_API_BASE_URL=http://127.0.0.1:8011 \
      node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
    ;;
  up|start|stop|ps|logs|config)
    test -f "$SETTINGS" || { printf 'Run bash scripts/reconcile.sh init first.\n' >&2; exit 1; }
    test ! -L "$SETTINGS"
    test "$(stat -c %a "$SETTINGS")" = 600 || { printf 'Local settings must have mode 600.\n' >&2; exit 1; }
    action=$1
    shift
    case "$action" in
      up) compose build api; compose up --no-build --force-recreate -d --wait --wait-timeout 240 "$@" ;;
      start) compose start --wait --wait-timeout 240 "$@" ;;
      stop) compose stop --timeout 130 "$@" ;;
      ps) compose ps "$@" ;;
      logs) compose logs --tail 100 "$@" ;;
      config) if [[ $# -eq 0 ]]; then compose config --quiet; else compose config "$@"; fi ;;
    esac
    ;;
  *) printf 'Usage: bash scripts/reconcile.sh {init|up|start|stop|ps|logs|config|frontend}\n' >&2; exit 2 ;;
esac
