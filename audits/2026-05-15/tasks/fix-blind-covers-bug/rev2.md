**Finding B: "Blind" Covers Silently Ignored — Review**

**Verdict: Approved.** Finding properly addressed.

---

### Core Fix Assessment

The `eff_pos`/`eff_tilt` fallback is correct:

```python
eff_pos = cur_pos if cur_pos is not None else last_pos
needs_pos = target_pos is not None and (
    eff_pos is None or abs(int(eff_pos) - target_pos) > tolerance
)
```

Three cases handled correctly:
- **No position, no history** (`eff_pos is None`): command sent. ✓
- **No position, has history** (`eff_pos = last_pos = prior target`): comparison against assumed state; no repeat if target unchanged. ✓
- **Has position**: original behavior preserved. ✓

### Refactoring Changes

- `self._last_commanded.get(entity_id, {})` + `if last:` — equivalent to old `get(entity_id)` + `if last is not None:` since stored values are always non-empty dicts. ✓
- `last_pos`/`last_tilt` hoisted before override block — harmless; downstream checks all guard on `is not None`. ✓
- Override block `cur_pos is None → pos_ok = True` — pre-existing behavior, comment now makes intent explicit. ✓

### Transit Grace Interaction

During `_TRANSIT_GRACE`, blind covers still require `cur_pos is not None` for correction commands (`needs_pos` check unchanged in that branch). This asymmetry is intentional and correctly noted in the comment — prevents command spam mid-movement. After grace expires, the outer `eff_pos` path takes over.

### Known Limitation (Not a Bug)

The assumed-position approach (`eff_pos = last_pos = last commanded`) silently accepts failed moves: if a blind cover cannot reach the commanded position, subsequent cycles see `eff_pos ≈ target_pos` and stop retrying. This is an inherent constraint of positionless hardware — no position feedback means no way to detect arrival failure. Periodic re-evaluation (the 15-min fallback) partially mitigates this, but it will not recover within the override window. This tradeoff is acceptable and matches the recommendation in the audit report ("allow the command to be sent on state transitions").

### Test Coverage

No new tests added. The blind-cover logic lives in `__init__.py` (HA-coupled), which is harder to unit-test than `logic.py`. Given the architecture, this is acceptable, but snapshot tests using a mocked `hass.states` would strengthen confidence in future regressions.

### Other Diff Changes

- `README.md` mobile app note: unrelated to finding, minor docs addition, no concern.
- `process_instructions.md` updates: process improvements only, correct.
- `todo.md`: marked done — accurate.

**No bugs, security issues, or blocking code quality concerns.**
