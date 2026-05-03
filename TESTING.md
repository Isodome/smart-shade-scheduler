# Testing Strategy

The integration has three distinct layers, each requiring a different testing approach.

---

## Layer 1 — Pure Python logic (unit-testable today, no HA needed)

### What's testable
- `ShadeManager._rule_matches()` — pure static function, takes a rule dict + sun/time values, returns bool
- `ShadeManager._fill_targets()` — pure static function, applies first-match-per-cover logic
- `ShadeManager._is_dnd_active()` — time arithmetic, can be tested by mocking `datetime.now()`
- `ShadeManager._override_duration()` — reads entity state, mockable
- The 3-pass evaluation order (priority → mode → fallback)

### How to run
```bash
pip install pytest
pytest tests/
```

### Example test
```python
def test_rule_matches_azimuth():
    rule = {"azimuth_above": 185, "elevation_above": 5}
    assert ShadeManager._rule_matches(rule, azimuth=200, elevation=10, hour=14, minute=0)
    assert not ShadeManager._rule_matches(rule, azimuth=180, elevation=10, hour=14, minute=0)
    assert not ShadeManager._rule_matches(rule, azimuth=200, elevation=3,  hour=14, minute=0)

def test_fill_targets_first_match_wins():
    rules = [
        {"mode": "KUEHLEN", "covers": ["cover.a"], "position": 0},
        {"mode": "KUEHLEN", "covers": ["cover.a"], "position": 50},  # should be skipped
    ]
    targets = {}
    ShadeManager._fill_targets("KUEHLEN", rules, targets, azimuth=200, elevation=10, hour=14, minute=0)
    assert targets["cover.a"]["p"] == 0

def test_three_pass_priority_wins():
    rules = [
        {"mode": "_priority", "covers": ["cover.a"], "elevation_below": 0, "position": 100},
        {"mode": "KUEHLEN",   "covers": ["cover.a"], "position": 0},
    ]
    targets = {}
    ShadeManager._fill_targets("_priority", rules, targets, 0, -5, 3, 0)
    ShadeManager._fill_targets("KUEHLEN",   rules, targets, 0, -5, 3, 0)
    assert targets["cover.a"]["p"] == 100  # priority rule won; KUEHLEN rule skipped
```

---

## Layer 2 — HA integration layer (requires pytest-homeassistant-custom-component)

### What's testable
- Config entry setup / teardown
- WebSocket commands (`ws_get_config`, `ws_save_rules`)
- Service registration (`clear_overrides`)
- Sensor entity attributes (`assumed_positions`, `overrides`)
- Options-update triggering reinit

### Setup
```bash
pip install pytest-homeassistant-custom-component
```

`pytest-homeassistant-custom-component` provides a mock HA `hass` fixture with:
- In-memory state machine
- Config entry management
- WebSocket test client
- Service call capture

### Example test
```python
async def test_ws_get_config(hass, hass_ws_client):
    entry = MockConfigEntry(domain="smart_shades", data={"mode_entity": "input_select.mode"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "smart_shades/get_config"})
    result = await client.receive_json()
    assert result["success"]
    assert "rules" in result["result"]
```

---

## Layer 3 — JavaScript panel (unit-testable today, no browser needed)

### What's testable without a browser
- `parseCondition()` — pure function, string → rule dict
- `validateCondition()` — pure function, string → `{ok, bad}`
- `formatCondition()` — pure function, rule dict → string
- Round-trip: `formatCondition(parseCondition(str)) === str`

### Setup
```bash
npm init -y
npm install --save-dev jest
# Extract the three functions into src/conditions.js, then:
npx jest
```

### Example tests
```js
test('parses all operators', () => {
  expect(parseCondition('az>150')).toEqual({ azimuth_above: 150 });
  expect(parseCondition('el>=5')).toEqual({ elevation_min: 5 });
  expect(parseCondition('h==8')).toEqual({ hour_eq: 8 });
  expect(parseCondition('m<=30')).toEqual({ minute_max: 30 });
});

test('round-trips cleanly', () => {
  const str = 'az>185 el>=5 h>6 h<10';
  expect(formatCondition(parseCondition(str))).toBe(str);
});

test('validates bad tokens', () => {
  expect(validateCondition('az>150 foo').ok).toBe(false);
  expect(validateCondition('az>150').ok).toBe(true);
});
```

### What requires a browser
- The full panel render (Shadow DOM, tab bar, IntersectionObserver)
- Cover picker autocomplete
- Save flow end-to-end

These can be tested with Playwright against a live HA instance (see Layer 4).

---

## Layer 4 — End-to-end against live HA (Playwright)

### What's testable
- Full panel load: tabs appear, rules render
- Add a rule, fill in fields, save → rules persist across reload
- Cover chip autocomplete and removal
- Condition badge ✓/✗ toggling
- Override icon appearing when a cover has an active override

### Setup
```bash
pip install playwright
playwright install chromium
```

### Approach
1. Start HA (or use the test instance at `homeassistant.local`)
2. Log in, navigate to `/smart-shades`
3. Assert tab bar is present
4. Assert rules from storage render correctly
5. Interact with the form, save, reload, re-assert

---

## Diagnosing the current breakage autonomously

When the integration "doesn't work" the fastest diagnosis path is:

### 1. Check HA logs over SSH
```bash
ssh root@homeassistant.local "cat /homeassistant/home-assistant.log | grep -i 'smart_shades\|error\|exception' | tail -50"
```

### 2. Hit the WebSocket API directly from Python
```python
# scripts/ws_test.py
import asyncio, json
import websockets

TOKEN = "YOUR_LONG_LIVED_TOKEN"
HOST  = "homeassistant.local"

async def main():
    async with websockets.connect(f"ws://{HOST}:8123/api/websocket") as ws:
        print(await ws.recv())  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        print(await ws.recv())  # auth_ok or auth_invalid
        await ws.send(json.dumps({"id": 1, "type": "smart_shades/get_config"}))
        print(json.dumps(json.loads(await ws.recv()), indent=2))

asyncio.run(main())
```

This immediately tells you whether:
- The integration loaded (`not_found` error → setup failed)
- The WebSocket command is registered (unknown command → panel.py didn't run)
- The config entry has rules (empty `rules` → storage issue)

### 3. Check integration setup status
```bash
ssh root@homeassistant.local \
  "cat /homeassistant/.storage/core.config_entries | \
   grep -A5 smart_shades"
```

### 4. Force a reload without full HA restart
Via the HA REST API (requires a token):
```bash
curl -X POST http://homeassistant.local:8123/api/config/config_entries/entry/ENTRY_ID/reload \
  -H "Authorization: Bearer TOKEN"
```

---

## Recommended next steps

1. **Immediately**: write Layer 1 unit tests — zero setup cost, covers the most critical logic
2. **Short term**: extract `parseCondition`/`validateCondition`/`formatCondition` into a separate `src/conditions.js` and add Jest tests
3. **Short term**: add `ws_test.py` script to the repo so the current breakage can be diagnosed in one command
4. **Medium term**: add `pytest-homeassistant-custom-component` for Layer 2

The Layer 1 + Layer 3 tests can run in CI (GitHub Actions) with no HA instance required.
