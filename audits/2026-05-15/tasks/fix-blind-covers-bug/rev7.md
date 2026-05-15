## Review — Fix Blind Covers Bug (rev7)

**Finding B status: Properly addressed.**

Both rev6 concerns have been resolved:

1. **`DEFAULT_TILT_DELAY` comment added** — `const.py:46` now reads `# Typical vertical shades take ~60s to close before tilt is reliable`. Justifies the 30→60 change inline. ✓

2. **`ts` reset comment restored** — `__init__.py:607` has `# Reset transit grace so it starts from the ACTUAL tilt move` back in place. ✓

The removed misplaced comment at line 493 (the divergence-check label that appeared above `last = self._last_commanded.get(...)`, before the override block) is a net improvement — the comment was in the wrong place. The real divergence check section at line 524 still has its label.

The removed override-block comment ("If current state is unknown...") is acceptable — the `cur_pos is None` arm in `pos_ok` is self-evident from the code.

---

**No bugs, no security issues, no remaining concerns.** Ready to commit.
