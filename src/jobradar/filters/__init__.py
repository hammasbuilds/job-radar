"""The filters, and one helper they share.

`rx` compiles a pattern once and keeps it. The filters hold several hundred
patterns between them (one per country per phrasing in `remote.py` alone),
which is more than the `re` module's own cache of 512; past that point every
call recompiled, and a replay of 7,345 postings took over ten minutes.
"""

from __future__ import annotations

import re
from functools import cache


@cache
def rx(pattern: str, flags: int = 0) -> re.Pattern:
    return re.compile(pattern, flags)
