# Smart Shade Scheduler

A Home Assistant custom integration for rule-based, sun- and time-aware automation of blinds, shutters and awnings — with intelligent manual-override detection and a full sidebar UI.

---

## Features

### Sidebar panel UI
A dedicated **Shades** entry appears in the HA sidebar. All rules for all modes are visible in a single scrollable view. A sticky tab bar at the top lets you jump directly to any mode section. No YAML, no config flows for day-to-day rule management.

### Mode-aware rules
Tie every rule to a **mode** — the state of an `input_select` entity. Whenever the mode changes, all covers instantly re-evaluate. The mode tab bar mirrors the input_select options exactly and updates automatically.

### Three-pass rule evaluation
Rules are evaluated in strict priority order for each cover:

1. **↑ Priority** — rules in this special mode always run first, regardless of the current mode. Use for safety rules that must always apply (e.g. retract awnings at night).
2. **Current mode** — the active input_select state (e.g. `KUEHLEN`, `BLENDSCHUTZ`).
3. **↓ Default** — rules in this special mode run only for covers that were not matched by any priority or current-mode rule. Use for sensible defaults.

Within each pass, rules are evaluated **top-to-bottom** and the **first match wins** per cover. Place specific (conditional) rules above catch-all rules.

### Rich condition syntax
Each rule optionally specifies conditions (space-separated tokens). All six comparison operators are supported:

| Token | Meaning |
|---|---|
| `az>150` / `az>=150` / `az<200` / `az<=200` / `az==180` | Sun azimuth |
| `el>5` / `el>=5` / `el<30` / `el<=30` / `el==10` | Sun elevation |
| `t>8:00` / `t>=8:00` / `t<22:00` / `t<=22:00` / `t==8:30` | Time of day |
| `home` | Only matches when someone is home |
| `away` | Only matches when nobody is home |

Multiple tokens are ANDed. An empty condition field is a catch-all.

`home` and `away` require a **presence entity** configured at setup (zone, binary_sensor, person, or device_tracker). If no entity is configured, these tokens are ignored.

### Intelligent manual-override detection
When a cover is **not where the automation last left it**, the integration assumes a person moved it manually and **pauses automation for that cover** (default 4 hours). The override clears automatically when:
- the override window expires, **or**
- the cover returns to the scheduled position on its own.

No event sniffing, no fragile ignore windows — the check happens lazily at each evaluation cycle.

### Cover chips with validation
Covers are entered as autocomplete chips populated from all `cover.*` entities in HA. Chips turn **orange** when the entity no longer exists, making stale rules easy to spot.

### Rule validation badges
Each rule row shows a **✓** or **✗** badge on the condition field. Invalid tokens are listed in a tooltip. Rows that have content but are missing both position and tilt are shown dimmed — they are kept in storage but not passed to the engine.

### Orphaned mode tabs
If a mode is removed from the input_select but still has rules, its tab is kept with a **⚠ dashed orange** border so no rules are silently lost. Orphaned tabs with no rules are removed automatically on the next save.

### Do-not-disturb window
Configurable time range (default 22:00–07:00) during which no automated movements are made. Can be overridden by a **binary sensor** (e.g. a sleep-tracking device) for smarter DND control.

### Daily override reset
All manual overrides are wiped at a configurable time each day (default 04:00) so every day starts clean.

### Override duration entity
An optional `input_number` entity (in hours) controls how long manual overrides last. Overrides the built-in 4-hour default and can be changed at runtime without reloading the integration.

### Real-time sensor entity
A sensor (`sensor.smart_shades_status`) is created with:
- **State**: current mode name
- **`assumed_positions`**: the position/tilt last commanded to each cover
- **`overrides`**: per-cover override start time, expiry time, and minutes remaining

### `smart_shades.clear_overrides` service
Immediately lifts manual override flags so automation resumes.

| Parameter | Description |
|---|---|
| `entity_id` *(optional)* | Specific cover to clear. Omit to clear all. |

### JSON-based rule storage
Rules are stored in Home Assistant's config entry options (`.storage/core.config_entries`). They are included in **HA backups**, can be exported/imported as JSON, and are versioned with git if your config directory is in source control.

---

## Installation

### Via HACS (recommended)
1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/Isodome/smart-shade-scheduler` with category **Integration**.
3. Install **Smart Shade Scheduler** and restart Home Assistant.

### Manually
1. Copy the `custom_components/smart_shades` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration** and search for **Smart Shade Scheduler**.
2. Select the **mode entity** (`input_select`) whose state names the current mode.
3. Optionally select a **DND binary sensor** and/or an **override duration input_number**.
4. Open the **Shades** panel in the sidebar to add and manage rules.
5. Use **Settings → Devices & Services → Smart Shade Scheduler → Configure** to adjust global settings (tolerance, DND times, daily wipe time).

---

## Rule fields

| Field | Description |
|---|---|
| **Covers** | One or more `cover.*` entities |
| **Condition** | Space-separated condition tokens (see syntax above). Empty = catch-all. |
| **Position** | Target position: 0 = fully closed, 100 = fully open |
| **Tilt** | Target tilt: 0 = fully closed, 100 = fully open |

Either position or tilt (or both) must be set for a rule to be active. Rules missing both are kept in storage but ignored by the engine.

---

## Global settings

| Setting | Default | Description |
|---|---|---|
| Position tolerance | 5 % | A cover is only moved if it deviates more than this from the target |
| DND start | 22:00 | No automated movements after this time |
| DND end | 07:00 | Automated movements resume at this time |
| Daily wipe time | 04:00 | All manual overrides are cleared at this time each day |

---

## Roadmap & backlog

### Planned
- **Temporary-position service** — set a cover position that holds only until the next scheduled evaluation, without triggering the manual-override timer. Useful for one-off adjustments that should self-correct.
- ~~**Rename "↓ Fallback" tab to "Default"**~~ — done.
- ~~**Send open/close signals at extremes**~~ — done. Position 100 sends `open_cover`, position 0 sends `close_cover`.
- **Month condition (`M`)** — add `M>=6 M<=8` tokens so rules can be restricted to specific months of the year (e.g. summer-only shading).
- ~~**Presence condition**~~ — done. `home`/`away` bare tokens; configure a presence entity (zone, binary_sensor, person, or device_tracker) at setup.

### Backlog
- ~~**Lenient condition parsing**~~ — done. All spaces are stripped before tokenising; `az > 150`, `az>= 150`, and `az>=150` are identical.
- **Cover groups** — allow a group entity (or a named list) to be used as a single cover target in a rule, so one rule can manage many covers without listing each one.
- **Jinja2 templates for position/tilt** — allow the position and tilt fields to accept a template string (e.g. `{{ 50 if az > 200 else 100 }}`), enabling smooth continuous adjustment instead of discrete breakpoints.

---

## Example mode setup

```yaml
input_select:
  storen_modus:
    name: Storen Modus
    options:
      - NORMAL
      - KUEHLEN
      - BLENDSCHUTZ
      - REGEN
      - AUS
```

An automation sets this entity based on weather forecast, time of day, etc. The Smart Shade Scheduler reacts instantly whenever the value changes.
