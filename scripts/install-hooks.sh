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

# Even the right repo must actually be private, and "could not check" is not
# "private": without gh, or offline, the push is refused. Set
# JOBRADAR_PUSH_UNVERIFIED=1 for one push when you have checked by hand.
private="unknown"
if command -v gh >/dev/null 2>&1; then
  private="$(gh repo view hammasbuilds/job-radar --json isPrivate -q .isPrivate 2>/dev/null || echo unknown)"
fi
if [ "$private" = "false" ]; then
  echo "pre-push: hammasbuilds/job-radar is PUBLIC. Refusing." >&2
  exit 1
fi
if [ "$private" != "true" ] && [ "${JOBRADAR_PUSH_UNVERIFIED:-}" != "1" ]; then
  echo "pre-push: could not confirm hammasbuilds/job-radar is private (gh: $private)." >&2
  echo "Check with: gh repo view --json isPrivate -q .isPrivate" >&2
  echo "then push with JOBRADAR_PUSH_UNVERIFIED=1 if it is." >&2
  exit 1
fi
HOOK

chmod +x "$hook"
echo "installed $hook"
