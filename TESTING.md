# Testing

## Python unit tests

Tests cover `rule_matches`, `evaluate_rules`, and `normalize_groups` — no Home Assistant installation required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
pytest tests/
```

## JavaScript unit tests

Tests cover `parseCondition`, `validateCondition`, and `formatCondition` in `conditions.js`.

```bash
cd custom_components/smart_shades/www
npx --node-options=--experimental-vm-modules jest
```

## HA integration tests (not yet implemented)

`pytest-homeassistant-custom-component` provides a mock `hass` fixture with an in-memory state machine, config entry management, WebSocket test client, and service call capture. This would let us test WebSocket commands (`ws_get_config`, `ws_save_rules`), config entry setup/teardown, the sensor entity attributes, and options-update triggering re-evaluation — all without a running HA instance.

```bash
pip install pytest-homeassistant-custom-component
```

## Browser E2E tests (not yet implemented)

Playwright against a live HA instance can cover the full panel: tab bar rendering, adding/saving rules, cover chip autocomplete, condition badge toggling, and override icons. Requires a running HA instance at `homeassistant.local`.

```bash
pip install playwright
playwright install chromium
```

## Deploy to Home Assistant

```bash
bash scripts/deploy.sh
```

Bundles the integration (excluding `node_modules` and caches), copies it to `homeassistant.local` over SSH, and restarts HA core.

## Diagnosing issues

**Check HA logs:**
```bash
ssh root@homeassistant.local "ha core logs 2>/dev/null | grep -i smart_shades | tail -30"
```

**Inspect live rules and config:**
```bash
scp root@homeassistant.local:/config/.storage/core.config_entries /tmp/ha.json
jq '.data.entries[] | select(.domain=="smart_shades") | .options' /tmp/ha.json
```

**Test the WebSocket API directly:**
```bash
python3 scripts/ws_test.py
```
Confirms the integration loaded, the WS command is registered, and the config entry has rules.

**Force-reload without a full HA restart** (requires a long-lived token):
```bash
curl -X POST http://homeassistant.local:8123/api/config/config_entries/entry/ENTRY_ID/reload \
  -H "Authorization: Bearer YOUR_TOKEN"
```
