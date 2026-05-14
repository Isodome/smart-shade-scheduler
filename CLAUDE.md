# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Python tests** (no HA installation required):
```bash
source .venv/bin/activate
pytest tests/
```

**JavaScript tests** (conditions parsing/formatting):
```bash
cd custom_components/smart_shades/www
npx --node-options=--experimental-vm-modules jest
```

**Run a single Python test file:**
```bash
pytest tests/test_rule_matches.py -v
```

**Deploy to Home Assistant:**
```bash
bash scripts/deploy.sh
```
Bundles the integration, copies to `homeassistant.local` via SSH, and restarts HA core.

**Diagnose live issues:**
```bash
ssh root@homeassistant.local "ha core logs 2>/dev/null | grep -i smart_shades | tail -30"
python3 scripts/ws_test.py  # verifies WS API and that rules are loaded
```

## Architecture

This is a **Home Assistant custom integration** (`DOMAIN = "smart_shades"`) that drives blinds/shutters based on sun position, time, presence, and a user-selected mode.

### Layer separation

```
logic.py          — pure Python, zero HA imports, all unit-testable
__init__.py       — ShadeManager: HA event wiring + override tracking; delegates evaluation to logic.py
panel.py          — registers the sidebar panel, static JS path, and WebSocket API
sensor.py         — exposes assumed_positions and active_overrides as HA sensor attributes
config_flow.py    — initial setup (mode entity, armed sensor) and options flow (tolerance, override duration, tilt delay, armed sensor)
www/              — vanilla Web Component (LitElement-style) frontend + conditions helpers
```

**`logic.py` must stay HA-free.** The conftest.py stubs out HA modules so tests can import it without a running HA instance.

### Rule data model

Rules are stored in the HA config entry options as a flat list of groups:

```json
{
  "mode": "_priority" | "_fallback" | "<mode_name>",
  "covers": ["cover.entity_id", ...],
  "conditions": [{"var": "azimuth|elevation|time|month|day|<custom>", "op": ">|<|>=|<=|==", "val": 150}],
  "action": {"position": 0-100, "tilt": 0-100}
}
```

`normalize_groups()` in `logic.py` handles migration from the old nested `{rules:[...]}` format — it is idempotent and must stay that way.

### Three-pass evaluation (`evaluate_rules` in `logic.py`)

1. **`_priority`** — always runs first, regardless of mode.
2. **Current mode** — matches the active `input_select` state.
3. **`_fallback`** — skipped when `block_fallback` is set for the current mode.

Within each pass, groups are evaluated top-to-bottom. Inside a group, the first rule whose conditions all match wins for that group's covers. A cover already assigned a target in an earlier pass is skipped in later passes.

### WebSocket API (`panel.py`)

- `smart_shades/get_config` — returns rules, mode options (including orphaned modes), current overrides.
- `smart_shades/save_rules` — persists rules and `mode_config` back to the config entry options. Triggers `_async_options_updated` which immediately re-evaluates.

### Override detection (`ShadeManager._do_evaluate`)

Override detection is **lazy**: at each evaluation cycle, if the cover's current position diverges from the last commanded position by more than tolerance, a manual override is recorded. The cover is then skipped until the override expires or the cover returns to the scheduled position. A 90-second transit grace period suppresses false positives while a cover is moving.

### Frontend (`www/smart_shades_panel.js`)

A single-file Web Component registered as `<smart-shades-panel>`. Communicates with HA exclusively via the WebSocket API. `conditions.js` handles parsing, validation, and round-trip formatting of condition strings — it is shared between the panel and tested independently with Jest.

### Cache busting

`panel.py:_JS_VERSION` (a string constant) **must be incremented** whenever `smart_shades_panel.js` changes, to bust the browser cache.

## Checklist for user-facing condition/token changes

When adding or changing condition syntax (operators, tokens, variables), update all of these:

1. **`const.py:BUILT_IN_VARS`** — add/modify the built-in var entry (`short`, `long`, `type`, `resolver`)
2. **`www/conditions.js:_DISPLAY`** — add JS-only display data (`hintExamples`, `llm`) keyed by `short`
3. **`www/smart_shades_panel.js` inlined conditions block** — mirror every change made to `conditions.js` (the two must stay in sync); also update the seed array passed to `initConditionSpec`
4. **`www/conditions.test.js`** — JS unit tests for parse/validate/format round-trips
5. **`tests/test_rule_matches.py`** — Python unit tests for the new logic
6. **`README.md`** — condition token table in the *Rich condition syntax* section
7. **`panel.py:_JS_VERSION`** — bump to bust browser cache after any JS change

> `conditions.js` is the testable source of truth for condition logic. `smart_shades_panel.js` inlines an identical copy (without `export` keywords) to avoid async-import timing issues with HA's view-transition system. Keep them in sync manually.
