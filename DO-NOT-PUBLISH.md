# Private repository only

This repo must never be pushed to a public remote.

## Why

**It is a record of a job search.** The database holds which roles were looked
at, which were rejected and why, and which were applied to. That is personal
information about an ongoing search, and it stops being private the moment the
repository is.

**It names companies and judges them.** Every row in the Killed screen is a
statement that a named company will not hire you and the sentence that proves
it. Those judgements are made by regular expressions, they are sometimes
wrong, and being wrong in public about a named employer is a different thing
from being wrong in a personal tool.

**`profile.py` is a CV in a dictionary.** It states what you can do and how
many years you have been doing it, which belongs on an application, not in a
searchable index.

## What is enforced

`.git/hooks/pre-push` refuses any remote that is not the private one. Git does
not copy hooks on clone, so **after cloning this repo anywhere, reinstall it**:

```bash
bash scripts/install-hooks.sh
```

Verify the remote is private at any time:

```bash
gh repo view --json isPrivate -q .isPrivate     # must print true
```

## If it is ever published by accident

Making the repo private again is not enough — assume the postings, the profile
and any pipeline notes were copied. Rotate nothing (there are no credentials
here by design), but do delete the repository rather than flipping its
visibility, because forks survive a visibility change.
