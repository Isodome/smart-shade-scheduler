## Review — Fix Blind Covers Bug (rev6)

**Finding B status: Properly addressed.**

The `eff_pos`/`eff_tilt` fallback correctly handles covers with no `current_position`:
- No state, no history → `eff_pos is None` → command sent unconditionally ✓
- No state, has history → falls back to `last_pos` for assumed-position comparison ✓
- Has state → original behavior ✓

Rev4 feedback incorporated:
- Dead suppression block removed ✓
- `entity_id in pos_cmds` granular tilt delay ✓
- `is_in_grace` flag + fall-through replaces the old `continue`, correctly handles blind covers during transit ✓

The `target_pos_changed` arm in `needs_pos` is logically correct: case 2 (`abs(eff_pos - target_pos) > tolerance`) handles most re-sends, but case 3 (`is_in_grace and target_pos_changed`) is necessary for the overshoot scenario (cover at 68 moving toward 70, target shifts to 64 — case 2 misses it, case 3 catches it).

---

**Two minor concerns:**

1. **`DEFAULT_TILT_DELAY` 30→60 is scope creep.** This doubles the default and is not related to the blind covers fix. No justification in the diff. Should either be a separate commit with rationale, or at minimum a comment explaining the empirical basis (e.g., "Somfy RTS covers need ~60s to fully travel before accepting tilt").

2. **Removed explanatory comment for `ts` reset in `_delayed_tilt`.** The line `self._last_commanded[eid]["ts"] = dt_util.now()` inside the delayed task is non-obvious — it re-stamps grace from the actual tilt move, not the decision time. The comment "Reset transit grace so it starts from the ACTUAL tilt move" explained *why* this is there. Without it, a future reader will reasonably ask why `ts` is being mutated inside an async closure after the sleep. Low severity but worth restoring.

---

**No bugs, no security issues.** Core finding B fix is correct and ready for commit once the `DEFAULT_TILT_DELAY` change is either justified or extracted.
