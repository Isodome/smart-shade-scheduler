**Finding properly addressed?** Yes — pile-up eliminated. But there's a critical bug that makes the fix deadlock every time.

---

## Critical: Deadlock in `_async_eval_loop`

`_async_eval_loop` acquires `_eval_lock`, then calls `async_evaluate_rules()` which tries to acquire it again:

```python
# _async_eval_loop:
async with self._eval_lock:              # acquires lock
    await self.async_evaluate_rules()   # → tries to acquire same lock → deadlock
```

```python
# async_evaluate_rules:
async with self._eval_lock:             # hangs forever
    await self._do_evaluate()
```

`asyncio.Lock` is not reentrant. Fix: call `_do_evaluate()` directly from the loop, or remove the lock from `async_evaluate_rules()` and rely solely on the loop's lock.

---

## Medium: High-priority events lose priority when task is running

When a high-priority event (mode change, HA start) fires while `_eval_task` is running, it sets `_needs_reeval = True` but the trailing-edge catch at line 348–349 always runs with the loop's original `high_priority` value. A low-priority loop will set `_last_low_prio_eval = now()` after the trailing eval, suppressing further low-prio evals for 240s — that's fine. But high-priority urgency is silently lost.

---

## Minor: `_async_options_updated` bypasses rate-limiting (intentional?)

Line 138 calls `await manager.async_evaluate_rules()` directly, bypassing the debounce. Once the deadlock is fixed (by removing the lock from `async_evaluate_rules()`), this path would skip the lock. Worth confirming intent — options changes probably *should* bypass debounce, but they'd also need lock protection.

---

## `process_instructions.md` changes

Both changes are good: the added `--allowedTools` flag gives peer Claude reviewers read access without interactive prompts, and the "output only your review response" instruction prevents preamble noise in `rev<N>.md` files.

---

**Bottom line:** Architecture is right — one task at a time with trailing-edge catch solves the pile-up. But the nested `_eval_lock` acquisition will deadlock on first run. The fix is a one-liner: replace `await self.async_evaluate_rules()` with `await self._do_evaluate()` inside `_async_eval_loop`.
