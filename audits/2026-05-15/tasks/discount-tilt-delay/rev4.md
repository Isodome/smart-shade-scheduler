## Review: discount-tilt-delay (rev4)

**Finding addressed:** Yes. Feature correctly implemented.

### Correctness

Formula `(delay - 5) * scale + 5` correctly implements scaled delay with 5s floor:
- 100% travel → full `delay`
- 0% travel → 5s (floor holds)
- Unknown position (`cur_pos is None`) → `pos_diffs[entity_id] = 100` → full delay. Safe default.

`max(5, ...)` guard is redundant given the math always yields ≥5 when `delay ≥ 5`, but harmless and defensive. Would only matter if `delay < 5`, where formula could yield < 5 — guard correctly clamps it. **Keep it.**

`scale` is capped at 1.0 only implicitly: `pos_diffs` stores `abs(int(cur_pos) - target_pos)`. If `cur_pos` state is somehow > 100 (malformed device), `scale > 1` and `actual_delay > delay`. Not dangerous — just slightly longer delay — but worth noting.

### Code quality

`pos_diffs.get(entity_id, 100)` at line 610: entity_id is in `pos_cmds` (checked by the `if entity_id in pos_cmds` guard at line 608), so `pos_diffs[entity_id]` is always set at that point. The `.get(..., 100)` fallback is dead code. Harmless, but slightly misleading — implies the key could be absent when it can't be.

`delay` fetched once before the loop (line 601) — correct, no per-cover inefficiency.

Closure capture of `actual_delay` via `d=actual_delay` default arg — correct pattern, consistent with existing `eid=entity_id, t=tilt` captures.

### Edge cases

- `delay == 0`: formula gives `(0-5)*scale + 5 = 5 - 5*scale`. For scale=1: 0. `max(5, 0)` → **5s**. This is a behavior change: user configured 0 delay expecting no delay, but gets 5s floor. If `delay == 0` the feature should be a no-op (no delay, no scaling). **Bug.**
- `delay < 5`: similarly, floor of 5 exceeds configured delay. User may have set 3s intentionally.

**Recommended fix:** Short-circuit when `delay == 0`. Optionally also when `delay <= 5` (floor equals full delay, scaling has no effect):

```python
if delay > 0:
    scale = pos_diffs.get(entity_id, 100) / 100.0
    actual_delay = (delay - 5) * scale + 5 if delay > 5 else delay
else:
    actual_delay = 0
```

Or simpler — skip scheduling a task at all when `actual_delay == 0` and send tilt immediately (avoids unnecessary async task overhead).

### Summary

One real bug: `delay=0` bypasses user intent by imposing 5s floor. All other concerns minor. Fix the zero-delay case before merge.
