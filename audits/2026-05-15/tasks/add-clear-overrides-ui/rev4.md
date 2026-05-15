## Peer Review — `add-clear-overrides-ui` (rev4)

**Verdict: One new bug found — requires fix before merge.**

---

### Rev2 fixes confirmed

Both rev2 blockers are resolved:
- `_JS_VERSION` bumped to `"105"` ✓
- `ws_clear_overrides` iterates all managers via `hass.data.get(DOMAIN, {}).values()` ✓

---

### Bug (blocking): `_load()` after success silently discards unsaved rule edits

`smart_shades_panel.js:1462` calls `await this._load()` after the WS call succeeds. `_load()` (lines 682–694) resets `this._groups`, `this._modeConfig`, `this._customVars`, and sets `this._dirty = false` — it replaces the entire in-memory edit state from the server.

If the user has unsaved rule changes when they click "Clear All Overrides", those changes are **silently discarded**. The confirm dialog only warns about override clearing, not data loss.

The intent is just to clear the orange override indicators. The WS response returns `{"success": True}` — no updated state. The correct fix is to update the local override list directly and re-render, skipping the full reload:

```js
root.querySelector('#clear-overrides-btn')?.addEventListener('click', async () => {
  if (!confirm('Clear all manual overrides and resume automation for all covers?')) return;
  try {
    await this._ws('smart_shades/clear_overrides');
    if (this._cfg) this._cfg.overrides = [];  // clear locally; avoids discarding unsaved edits
    this._render();
  } catch (e) {
    alert(`Error: ${e.message ?? e}`);
  }
});
```

The existing `_load()` call after `ws_save_rules` (line 859) is appropriate there because the rules were just persisted. Here the rules are untouched, so a full reload is the wrong tool.

---

### No other issues

- `hasattr` duck-typing vs `isinstance(m, ShadeManager)` in `__init__.py` is inconsistent but not a bug; `hass.data[DOMAIN]` only holds `ShadeManager` instances.
- No authorization gap — consistent with `ws_save_rules` and HA's own WS auth layer.
- `vol.Optional("entity_id")` schema is forward-compatible with future per-entity clearing.
- Button placement and confirm dialog text are appropriate.

---

### Summary

| Severity | Issue |
|----------|-------|
| **Blocking** | `_load()` call discards unsaved rule edits — replace with `this._cfg.overrides = []; this._render()` |
