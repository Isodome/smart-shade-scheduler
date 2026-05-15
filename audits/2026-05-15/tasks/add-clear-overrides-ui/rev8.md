## Review: `add-clear-overrides-ui` — rev8

**Verdict: APPROVE.** Implementation correct. No bugs, no security issues. Notes below.

---

### Correctness

**`ws_clear_overrides` handler** — logic sound:
- `isinstance(manager, ShadeManager)` guard correct; avoids hitting non-manager entries in `hass.data[DOMAIN]`
- `found = False` / error path handles zero-manager state correctly
- `msg.get("entity_id")` correctly passes `None` when absent → `clear_overrides(None)` clears all

**`clear_overrides` contract** (`__init__.py:258`) — clears both `_overrides` and `_last_commanded`, then calls `_notify()`. The WS handler additionally calls `async_schedule_evaluation(high_priority=True)` after. Mirrors pattern from `_handle_clear_overrides` service. Potentially triggers evaluation twice (once via `_notify()` listeners, once via the explicit call), but `async_schedule_evaluation` uses debouncing so this is benign.

**Frontend local state** — `this._cfg.overrides = []` is correct. `overrides` is `string[]` (entity IDs), clearing to `[]` is right. Avoids re-fetch that would discard unsaved rule edits. `_render()` then reflects empty overrides immediately.

---

### Minor observations

1. **`entity_id` schema param unused by UI** — defined as `vol.Optional("entity_id"): str` but frontend always clears all. Good extension point; no issue.

2. **`@callback` appropriateness** — all ops inside handler (`dict.clear()`, `_notify()`, scheduling) are non-blocking synchronous. `@callback` is correct.

3. **No entry-level scoping** — WS handler clears overrides across *all* managers, while `ws_get_config` reads only `entries[0]`. Mismatch pre-exists in this codebase; not introduced here.

4. **JS version bump** — `_JS_VERSION` correctly incremented to `"105"`.

5. **`TYPE_CHECKING` guard** — `from . import ShadeManager` inside `if TYPE_CHECKING` at module level, then unconditional runtime import inside `ws_clear_overrides`. Standard circular-import pattern; correct.

---

### Security

No new attack surface. WS auth is HA's existing mechanism, consistent with all other handlers (`ws_save_rules` etc.). No permission escalation.

---

**No blocking issues. Ready to commit.**
dict.pop`.
- Authorization: consistent with `ws_save_rules` (no `require_admin` on either) — not a new regression.
- Multi-entry handling: all managers cleared, single response returned — correct.
- `entity_id` param present in WS schema but not exposed in UI — fine stub for future per-cover clearing.
