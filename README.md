# Smart Shade Scheduler

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A Home Assistant custom integration for rule-based, sun- and time-aware automation of blinds, shutters and awnings — with intelligent manual-override detection and a full sidebar UI.

---

## Features

### Sidebar panel UI
A dedicated **Shades** entry appears in the HA sidebar. Rules are organised into **Cover Group Cards** inside mode sections. A sticky tab bar lets you jump directly to any mode. Each card defines a set of covers and an ordered list of condition→action rows. No YAML, no config flows for day-to-day rule management.

### Mode-aware rules
Tie every rule to a **mode** — the state of an `input_select` entity. Whenever the mode changes, all covers instantly re-evaluate. The tab bar mirrors the input_select options exactly and updates automatically.

### Three-pass rule evaluation
Rules are evaluated in strict priority order for each cover:

1. **↑ Priority** — always runs first, regardless of the active mode. Use for safety rules that must always apply (e.g. retract awnings at night or in high wind).
2. **Current mode** — the active input_select state (e.g. `NORMAL`, `RAIN`, `COOLING`).
3. **↓ Default** — runs only for covers not matched by any priority or current-mode rule. Use for sensible catch-all positions.

Within each pass, Cover Groups are evaluated top-to-bottom. Inside each group, condition rows are evaluated top-to-bottom and the **first match wins** for that group's covers. Place specific conditional rows above catch-all rows.

### Rich condition syntax
Each rule optionally specifies conditions (space-separated tokens). Both short and long names are accepted (`az` and `azimuth` are equivalent).

**Range conditions** — true continuously while the value is within the range:

| Token | Meaning |
|---|---|
| `az>150` / `az>=150` / `az<200` / `az<=200` / `az==180` | Sun azimuth (°) |
| `el>5` / `el>=5` / `el<30` / `el<=30` / `el==10` | Sun elevation (°, negative = below horizon) |
| `t>8:00` / `t>=8:00` / `t<22:00` / `t<=22:00` / `t==8:30` | Time of day (HH:MM) |
| `mo>=4` / `mo<=9` | Month (1–12) |
| `d<=4` / `d==0` | Day of week (0=Mon … 6=Sun) |
| `name>value` | Custom sensor variable (see below) |

**Crossing conditions** — true only in the single evaluation cycle when a threshold is crossed:

| Token | Meaning |
|---|---|
| `az=185` / `el=10` / `t=7:30` | Numeric threshold crossed in either direction |
| `az=^185` / `el=^10` | Threshold crossed while **rising** (e.g. `el=^10` = sunrise above 10°) |
| `az=v185` / `el=v10` | Threshold crossed while **falling** (e.g. `el=v10` = sunset below 10°) |

Crossing conditions never fire on the first evaluation after HA restarts. If a value skips over a threshold between evaluations, the crossing is still detected. Time (`t`) is monotonic — `=v` never applies to it.

Multiple tokens are ANDed. An empty condition field is a catch-all that always matches.

### Custom sensor variables
Bind short names to HA entities or Jinja2 templates via **☰ → Custom Variables** in the panel:

```
alarm=sensor.next_alarm_time
temp=sensor.living_room_temperature
motion={{states('binary_sensor.bedroom_motion') == 'on' and 1 or 0}}
```

The name then works as a condition token in any rule:

```
alarm<800 el<10    → close before alarm if sun is low
temp>26            → open vent cover when room is warm
```

**State coercion** — entity states are coerced to a number in this order:

| State format | Example | Coerced to |
|---|---|---|
| ISO datetime with timezone | `2026-05-11T04:40:00+00:00` | HHMM int in HA local time (`440`) |
| Time string `HH:MM` or `HH:MM:SS` | `07:30:00` | HHMM int (`730`) |
| Numeric string | `21.5` | float (`21.5`) |
| `on` / `off` | `on` | `1` / `0` |
| Anything else | `unavailable`, `unknown`, … | unavailable |

If coercion fails or the entity does not exist, any condition referencing that variable evaluates to `False` (fail-safe). The Variables dialog shows the current resolved value of every variable (built-ins and custom) from the last evaluation cycle.

### Per-mode options
Each mode (except ↑ Priority and ↓ Default) has two toggles in the panel:

- **Block fallback** — when active, the ↓ Default pass is skipped entirely for this mode. Covers not matched by any rule are left untouched. Useful for modes like RAIN where you only want to control specific covers.
- **Force on switch** — when the mode switches to this mode, manual overrides are cleared for all covers that have a rule in this mode, so they immediately move to their scheduled positions.

### Intelligent manual-override detection
When a cover is not where the automation last left it, the integration assumes a person moved it manually and pauses automation for that cover. The override clears automatically when the override window expires or the cover returns to the scheduled position on its own.

No event sniffing, no fragile ignore windows — the check happens lazily at each evaluation cycle.

### Cover chips with validation
Covers are entered as autocomplete chips from all `cover.*` entities in HA. Chips turn orange when the entity no longer exists, making stale rules easy to spot.

### Orphaned mode tabs
If a mode is removed from the input_select but still has rules, its tab is kept with a dashed orange border so no rules are silently lost.

### Armed sensor
An optional `binary_sensor` controls whether automation runs. When the sensor is `on`, automation is armed. When `off`, all evaluation is skipped. If no sensor is configured, automation always runs.

### Real-time sensor
A sensor (`sensor.smart_shade_scheduler`) exposes:
- **State**: current mode name
- **`assumed_positions`**: the position/tilt last commanded to each cover
- **`overrides`**: per-cover override start time, expiry time, and minutes remaining

### `smart_shades.clear_overrides` service
Immediately lifts manual override flags so automation resumes.

| Parameter | Description |
|---|---|
| `entity_id` *(optional)* | Specific cover to clear. Omit to clear all. |

### Import / Export / LLM prompt
The hamburger menu (☰) in the top-right of the panel provides:
- **Custom Variables** — bind short names to HA entities or templates
- **Generate LLM Prompt** — copies a full system description and current rule set to the clipboard, ready to paste into any AI assistant
- **Export / Import** — JSON backup and restore of all rules
- **Integration Settings** — jump directly to the HA integrations config page

### JSON-based rule storage
Rules are stored in HA's config entry options (`.storage/core.config_entries`). Included in HA backups, exportable as JSON, and versionable with git.

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
3. Optionally select an armed sensor (binary_sensor) and/or an override duration entity.
4. Open the **Shades** panel in the sidebar to add and manage rules.
5. Use **Settings → Devices & Services → Smart Shade Scheduler → Configure** to adjust global settings (tolerance, override duration, tilt delay).

---

## Rule structure

| Field | Description |
|---|---|
| **Covers** | One or more `cover.*` entities the card applies to |
| **Condition** | Space-separated condition tokens (see above). Empty = catch-all |
| **Position** | Target position: 0 = fully closed, 100 = fully open |
| **Tilt** | Target tilt: 0 = fully closed, 100 = fully open |

At least one of position or tilt must be set for a row to be active.

---

## Global settings

| Setting | Default | Description |
|---|---|---|
| Position tolerance | 5 % | A cover is only moved if it deviates more than this from the target |
| Override duration | 120 min | How long a manual move suppresses automation |
| Tilt delay | 30 s | Seconds between position and tilt commands |

---

## Example mode setup

```yaml
input_select:
  shade_mode:
    name: Shade Mode
    options:
      - NORMAL
      - COOLING
      - RAIN
      - OFF
```

An automation sets this entity based on weather forecast, time of day, or manual input. The Smart Shade Scheduler reacts instantly whenever the value changes.

---

## Roadmap & backlog

### Known Bugs
- **Tilt position doesn't work** — sometimes gets stuck and fails to update.
- **Overrides are broken** — manual override detection not functioning as expected.
- **Validation checkmark is inconsistent** — UI validation state doesn't always reflect current rules correctly.
- In the mobile app, the panel hides the apps own controls and is full screen.

### Planned
- **Temporary-position service** — set a cover position/tilt that holds only until the next rule evaluation, without triggering the manual-override timer. Useful for one-off adjustments that should self-correct.
- **One-shot rule flag** — mark a rule as "fire once per day". After it fires for a cover, the cover is left alone until the daily reset, even if conditions remain true. Useful for morning-open rules that should not re-enforce after a manual adjustment.

### Backlog
- **Simulator** — a panel view that lets you scrub through a day (time, sun azimuth/elevation, month) and see in real time which rules would fire and what position/tilt each cover would end up at. Useful for validating rules before deploying them.
- **Jinja2 templates for position/tilt** — accept a template string (e.g. `{{ 50 if az > 200 else 100 }}`), enabling continuous adjustment instead of discrete breakpoints.

---

## License

GPL-3.0-only — see [LICENSE](LICENSE).
