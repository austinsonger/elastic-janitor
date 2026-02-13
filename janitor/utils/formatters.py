"""
Formatting utilities for dates, sizes, and other data.
"""
from datetime import datetime, timezone


def parse_epoch_millis(ms):
    """Convert epoch milliseconds to datetime."""
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def size_to_bytes(s):
    """Convert size string like '1.2gb' to bytes."""
    if not s:
        return 0
    s = s.strip().lower()
    mult = 1
    if s.endswith("kb"):
        mult = 1024
        num = s[:-2]
    elif s.endswith("mb"):
        mult = 1024**2
        num = s[:-2]
    elif s.endswith("gb"):
        mult = 1024**3
        num = s[:-2]
    elif s.endswith("tb"):
        mult = 1024**4
        num = s[:-2]
    elif s.endswith("b"):
        num = s[:-1]
    else:
        num = s
    try:
        return float(num) * mult
    except Exception:
        return 0


def bytes_to_human(b):
    """Convert bytes to human readable format."""
    if b < 1024:
        return f"{b}b"
    elif b < 1024**2:
        return f"{b/1024:.2f}kb"
    elif b < 1024**3:
        return f"{b/1024**2:.2f}mb"
    elif b < 1024**4:
        return f"{b/1024**3:.2f}gb"
    else:
        return f"{b/1024**4:.2f}tb"

