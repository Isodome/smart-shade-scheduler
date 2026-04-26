# Smart Shade Scheduler

A Home Assistant custom integration for rule-based, sun-aware automation of blinds, shutters and awnings — with intelligent manual-override detection.

## Features

### Mode-aware rules
Tie every rule to a **mode** — the state of any entity (e.g. an `input_select`). Whenever the mode changes (e.g. `KUEHLEN` → `NORMAL`) all covers instantly re-evaluate. Rules are ordered; **the first match wins** for each cover, so you can layer specific sun-angle conditions on top of catch-all defaults.

### Sun-angle conditions
Each rule can require:
- `Sun azimuth above X°` — targets west-facing covers in the afternoon
- `Sun elevation above X°` / `Sun elevation below X°` — targets low-angle glare or high-summer heat

### Intelligent manual-override detection
When a cover is **not where the automation last left it**, the integration assumes a person moved it manually and **pauses automation for that cover for 4 hours**. The override clears automatically when:
- the 4-hour window expires, **or**
- the scheduled position matches the actual position again (e.g. the user moved it back)

No event sniffing, no fragile ignore windows — the check happens lazily at each evaluation cycle.

### Do-not-disturb window
Configurable time range (e.g. 22:00–07:00) during which no automated movements are made.

### Daily override reset
All manual overrides are wiped at a configurable time each day (default 04:00) so the new day starts clean.

### Fully UI-configurable
No YAML required. Add, edit, reorder and delete rules from **Settings → Devices & Services → Smart Shade Scheduler → Configure**.

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

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Smart Shade Scheduler**.
3. Select the **mode entity** (e.g. `input_select.storen_modus`) whose state names the current mode.
4. Click **Configure** on the integration card to add rules and adjust global settings.

---

## Rules

Each rule has:

| Field | Required | Description |
|---|---|---|
| Name | ✓ | Human-readable label |
| Mode | ✓ | State value of the mode entity this rule applies to |
| Covers | ✓ | One or more `cover.*` entities |
| Azimuth above | — | Only match when sun azimuth > value |
| Elevation above | — | Only match when sun elevation > value |
| Elevation below | — | Only match when sun elevation < value |
| Target position | — | 0 = closed, 100 = open |
| Target tilt | — | 0 = closed, 100 = open |

Rules are evaluated **top-to-bottom**; the first rule that matches a cover sets its target. Place specific (sun-conditional) rules above catch-all rules.

---

## Services

### `smart_shades.clear_overrides`
Immediately clears manual override flags so automation resumes.

| Parameter | Description |
|---|---|
| `entity_id` *(optional)* | Specific cover to clear. Omit to clear all. |

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
