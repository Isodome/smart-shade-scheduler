Two findings, both minor:

**1. `async_schedule_evaluation` missing `@callback`** (`__init__.py:332`)

Called from `@callback` methods but not decorated itself. HA will log a warning in recent versions since `async_create_task` is invoked from a non-`@callback` context. Fix: add `@callback`.

**2. `_eval_lock` is now redundant** (`__init__.py:173, 360`)

`_eval_task` already serializes evals — only one `_async_eval_loop` runs at a time. The lock inside that loop is always uncontested. Not harmful but dead weight. Can drop both the `asyncio.Lock()` allocation and `async with self._eval_lock` wrapper, which lets `_do_evaluate` be a plain `await` without the lock overhead.

---

Finding is properly addressed. No bugs, no security issues. Logic (trailing-edge reeval, cooldown, high-prio escalation) is correct. The `@callback` conversion of `_async_options_updated` is valid — HA calls `result = listener(hass, entry)` and only awaits if it's a coroutine.
