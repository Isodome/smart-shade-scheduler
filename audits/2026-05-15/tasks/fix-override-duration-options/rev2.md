Two issues found:

**1. Comment violates CLAUDE.md style** (`__init__.py:352`)
```python
# The user explicitly requested minutes for this entity
```
CLAUDE.md: "Don't reference the current task, fix, or callers." Delete it — the unit is self-evident from `timedelta(minutes=...)`.

**2. Silent breaking change for existing users**
Old code: `timedelta(hours=float(state.state))`. New code: `timedelta(minutes=...)`. Anyone with the entity already configured and set to e.g. `2` (intending 2 hours) now gets 2 minutes — 60× reduction. This is the correct fix since `CONF_OVERRIDE_DURATION` is already in minutes (`const.py:57`), but it's a behavioral breaking change worth noting in a changelog or migration note.

Everything else is correct:
- `_opt()` falls back `options → data`, so existing installs with entity in `entry.data` still work ✓
- `"unknown"/"unavailable"` guard prevents bad state reads ✓
- `TypeError` addition handles edge cases ✓
- Options flow saves entity properly; initial config flow already had entity field ✓
- `suggested_value` pattern correct for optional entity selectors ✓

Fix: remove that comment.
