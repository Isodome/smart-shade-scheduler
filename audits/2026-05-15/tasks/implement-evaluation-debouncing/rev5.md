`async_evaluate_rules` fully removed — no dangling callers.

The implementation looks correct. Key findings:

**`@callback` on `_async_options_updated` — valid.** HA's `add_update_listener` fires via `async_run_hass_job`, which handles both coroutines and `@callback` functions. Since the function now only calls synchronous `@callback` methods, the change is correct.

**Rate-limiting logic — one subtle behavior worth knowing.**
Low-prio events during the 240s cooldown are dropped *before* the running-task check, meaning they don't set `_needs_reeval`. This is intentional — a running eval already covers what they'd do — but the 15-min scan interval is the only safety net if a low-prio event is dropped while no task is running.

**`_needs_reeval` trailing-edge — correct.** Reset happens at top of loop iteration (before `_do_evaluate`), so any event that fires during `await _do_evaluate()` correctly sets the flag and triggers a re-loop.

**`finally: self._eval_task = None` — correct.** Exception in `_do_evaluate` propagates out, cleans up, next `async_schedule_evaluation` spawns fresh task. HA logs the exception as unhandled task error (acceptable).

**Lock removal — safe.** All callers are `@callback` on the event loop (single-threaded). No concurrent access possible.

**No security issues.** No new external inputs, no injection surfaces.

One cosmetic nit: line 153 has trailing whitespace on the blank line between `_overrides` and the comment block. Not a correctness issue.

Issue is properly addressed.
