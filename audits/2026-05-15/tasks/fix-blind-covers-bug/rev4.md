You've hit your limit · resets 4pm (Europe/Zurich)
iew (rev3)**

**Verdict: Approved with minor notes.** Finding properly addressed. Rev3 also correctly fixes the per-cover tilt delay bug from rev2 and adds tilt responsiveness during transit grace.

---

### Core Finding B

`eff_pos`/`eff_tilt` fallback preserved from rev2. Behavior unchanged and correct:
- No position + no history (`eff_pos is None`): command sent. ✓
- No position + has history (`eff_pos = last_pos`): assumed-position comparison. ✓
- Has position: original behavior. ✓

---

### New Changes (Rev2 → Rev3)

**1. Per-cover tilt delay — clear bug fix.**

```python
# rev2 (buggy)
if pos_cmds:
# rev3 (correct)
if entity_id in pos_cmds:
```

Rev2 delayed ALL tilts if any cover had a position command. Rev3 delays only tilts for covers that are also moving position. Correct.

**2. Transit grace fall-through (`is_in_grace` flag) — correct intent, minor over-trigger risk.**

The old `continue` during grace suppressed tilt commands even when the tilt target changed. The new flag + fall-through allows tilt to fire if `target_tilt_changed`. This matches the stated goal.

Edge case: the `(is_in_grace and target_pos_changed)` condition forces a re-send even when `abs(eff_pos - target_pos) <= tolerance`. This is intentional for mid-transit target changes, but will over-trigger when target shifts by less than `tolerance` (e.g., target 30→32, tolerance 5). The cover gets an extra command it doesn't need. Acceptable for most hardware but worth noting.

**3. Suppression block (`lines 578–582`) — unreachable dead code.**

```python
if is_in_grace:
    if needs_pos and not target_pos_changed and cur_pos is None:
        needs_pos = False
```

This can never fire: `is_in_grace = True` requires `last` to be non-empty. For `eff_pos is None` to hold, `cur_pos is None AND last_pos is None`. For `last_pos is None`, `last["p"] is None`. For `target_pos_changed = False`, `target_pos == last_pos == None`. But `target_pos is None` means the outer `needs_pos = target_pos is not None and (...)` evaluates to `False` before the suppression block is reached. The block is dead code. Recommend removing both lines to reduce confusion.

**4. `_last_commanded["ts"]` reset after delayed tilt — preserved, correct.**

Comment removed but code retained (`__init__.py:615`). Grace period correctly restarts from the actual tilt command time, not from when the decision was made. ✓

**5. `last_commanded` update in `else` branch — correct.**

When `needs_move = False`, `p`/`t` are updated but `ts` is not. This is correct: the target tracking updates without resetting grace. ✓

---

### Pre-existing Limitation (Not Introduced Here)

Delayed tilt tasks do not re-check `self._overrides` before executing. If a manual override is recorded after a tilt task is created but before it fires, the stale tilt still sends. Not a regression; the task cancellation (Finding C fix) covers the re-schedule case. The remaining window (new override between schedule and fire) is a known residual risk.

---

### Summary

Two actionable items:

1. **Remove the suppression block** (`__init__.py:578–582`) — dead code, adds confusion. No behavior change.
2. **(Optional) Document the `is_in_grace and target_pos_changed` over-trigger** if you want sub-tolerance target changes during transit to NOT cause re-sends.

No bugs, security issues, or blocking concerns. Both Finding B and Finding C are properly addressed.
