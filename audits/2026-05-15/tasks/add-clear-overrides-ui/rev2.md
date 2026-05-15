## Peer Review — `add-clear-overrides-ui`

**Verdict: Approve with one required fix before merge.**

---

### Bug (blocking): `_JS_VERSION` not bumped

`panel.py:30` still reads `_JS_VERSION = "104"`. The diff modifies `smart_shades_panel.js` but does not increment this constant. Per `CLAUDE.md`:

> `panel.py:_JS_VERSION` — bump to bust the browser cache after any JS change

Browsers will serve the cached JS without the new button. Fix: increment to `"105"` (or current + 1).

---

### Bug (minor): WS handler targets only `entries[0]`

`panel.py:181` — `entry = entries[0]` — only clears overrides on the first config entry's manager.

The existing HA service (`__init__.py:96–98`) correctly iterates all managers:

```python
for m in hass.data.get(DOMAIN, {}).values():
    if isinstance(m, ShadeManager):
        m.clear_overrides(entity_id)
```

The WS handler should mirror this pattern. In practice there is likely only one entry, but the inconsistency is a latent bug and diverges from the established pattern in the same codebase.

---

### OK: Authorization

No admin check, but consistent with `ws_save_rules` and other WS handlers in the file. HA WS connections require authentication; this is an acceptable level of access control for a local integration.

---

### OK: UI flow

- `confirm()` dialog text is clear and accurate.
- `_load()` after success correctly refreshes override indicators.
- Button placement in the Tools section is appropriate for a bulk state-clearing action.
- `optional entity_id` in the schema is correct — the `clear_overrides` method handles `None` (clears all) safely.

---

### Summary

| Severity | Issue |
|----------|-------|
| **Blocking** | `_JS_VERSION` not bumped — new button won't load in browser |
| **Minor** | WS handler uses `entries[0]` instead of iterating all managers like the HA service does |
