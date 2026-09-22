#!/usr/bin/env bash
# Refuse to push this repository anywhere public.
#
# Git does not copy hooks on clone, so this has to be re-run after every fresh
# checkout. See DO-NOT-PUBLISH.md for why the repo is private.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
hook="$root/.git/hooks/pre-push"

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Blocks a push to any remote that is not a known-private one.
set -euo pipefail

remote_url="${2:-}"

case "$remote_url" in
  *hammasbuilds/job-radar*) ;;
  *)
    echo "pre-push: refusing to push job-radar to '$remote_url'." >&2
    echo "This repository holds a personal job search and judgements about" >&2
    echo "named companies. See DO-NOT-PUBLISH.md." >&2
    exit 1
    ;;
esac

# Even the right repo must actually be private.
if command -v gh >/dev/null 2>&1; then
  private="$(gh repo view hammasbuilds/job-radar --json isPrivate -q .isPrivate 2>/dev/null || echo unknown)"
  if [ "$private" = "false" ]; then
    echo "pre-push: hammasbuilds/job-radar is PUBLIC. Refusing." >&2
    exit 1
  fi
fi
HOOK

chmod +x "$hook"
echo "installed $hook"
