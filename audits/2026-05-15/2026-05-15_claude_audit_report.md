# Smart Shade Scheduler — Python Engine Audit

**Date:** 2026-05-15  
**Model:** Claude Sonnet 4.6  
**Scope:** `logic.py`, `__init__.py`, `const.py`, `panel.py` (API surface), `sensor.py`, `config_flow.py`  
**Reviewer stance:** senior engineer, focus on correctness, robustness, and simplicity

---

## 1. Critical: `normalize_groups` is dead / its output is unreadable

**`logic.py:144–161`, `__init__.py:391`**

`normalize_groups` converts the old nested format `{rules:[{conditions, action}]}` into flat groups `{conditions, action}`. But `fill_targets` reads `group.get("rules", [])` — the old format. After normalization, that key is gone, so `fill_targets` returns an empty iterator and **no rules fire**.

`normalize_groups` is also never called in `_do_evaluate`. The stored format is still the nested one (`rules: [...]`) as confirmed by every test in `test_evaluate_rules.py`. CLAUDE.md's description of the "current stored format" (flat `{conditions, action}`) describes `normalize_groups`'s **output**, not what's actually stored.

Two equally valid fixes:
- Keep the nested stored format; update `normalize_groups` to wrap flat groups back to nested so it's truly idempotent both ways. OR
- Migrate stored format to flat; update `fill_targets` to read `{conditions, action}` directly (simpler evaluation loop). Call `normalize_groups` at the top of `_do_evaluate`.

The second is cleaner: each group = one rule, evaluation loop is flat `for group in groups`. But it's a breaking change to stored data and requires `normalize_groups` be called at read time (or a one-time migration).

---

## 2. High: Armed entity listener not reinstated on options change

**`__init__.py:186–192`, `125–131`**

`_async_options_updated` calls `reinit_mode_listener()` only. If the user changes the armed entity in the options flow, the old listener stays registered, the new entity is never watched. The `armed` guard then reads state correctly from `_is_armed()` (which does a live state read), so the security is intact — but state-change-triggered re-evaluation stops working for the new armed entity until HA restarts.

Fix: add `self._reinit_armed_listener()` call in `_async_options_updated`.

---

## 3. High: Tilt delay task not tracked; leaks on unload

**`__init__.py:502–506`**

`hass.async_create_task(_delayed_tilts())` is fire-and-forget. If the config entry is unloaded while the task sleeps (30 s delay), it wakes up and calls `_send_tilt` on covers that may belong to an unloaded manager. Store the task reference and cancel it in `unload()`.

```python
# in __init__
self._pending_task: asyncio.Task | None = None

# in unload()
if self._pending_task and not self._pending_task.done():
    self._pending_task.cancel()
```

---

## 4. Medium: `datetime.now()` — naive datetime, timezone unsafe

**`__init__.py:389, 452, 484`, `sensor.py:49`**

`datetime.now()` returns local system time with no timezone info. HA runs in a Docker container whose system timezone is often UTC, while the HA configured timezone can differ. Use `dt_util.now()` (from `homeassistant.util.dt`) which returns an aware datetime in HA's local timezone. All timedelta comparisons (`age >= self._override_duration()`) work correctly regardless, but `since.isoformat()` in the sensor will show UTC instead of the user's timezone.

---

## 5. Medium: `_build_custom_resolvers` re-parsed every evaluation cycle

**`__init__.py:339–368`, called at `__init__.py:396`**

The method parses a multiline string and constructs closures on every call. It's invoked on every sun-change event (~every few minutes). Cache the result and invalidate in `_async_options_updated`.

```python
self._custom_resolvers: dict | None = None  # None = needs rebuild

def _get_custom_resolvers(self):
    if self._custom_resolvers is None:
        self._custom_resolvers = self._build_custom_resolvers()
    return self._custom_resolvers

# in _async_options_updated:
manager._custom_resolvers = None
```

---

## 6. Medium: Evaluation tasks pile up under rapid events

**`__init__.py:283, 289, 293, 297`**

All four event callbacks call `hass.async_create_task(self.async_evaluate_rules())`. The lock serializes execution but tasks accumulate in the event loop queue. On a sunny morning, sun position updates every ~60 s — fine. But a mode change firing the handler + interval firing simultaneously queues 2 tasks; the lock runs them back-to-back even when the second is redundant.

A simple guard: keep a reference to the current pending task and cancel it if a new one arrives before the lock is acquired.

---

## 7. Low: Encapsulation breaks — private attributes read cross-class

**`panel.py:135`, `sensor.py:50–58`**

`manager._var_values`, `manager._last_commanded`, `manager._override_duration()` accessed from outside `ShadeManager`. These should be public properties:

```python
@property
def var_values(self) -> dict:
    return self._var_values

@property
def assumed_positions(self) -> dict:
    return dict(self._last_commanded)
```

---

## 8. Low: Debug/introspection code left in production

**`panel.py:38–39`**

```python
sig = inspect.signature(StaticPathConfig)
_LOGGER.debug("StaticPathConfig signature: %s", sig)
```

Exploratory code; remove both lines.

---

## 9. Low: `_TRANSIT_GRACE` is an instance attribute

**`__init__.py:149`**

```python
self._TRANSIT_GRACE = 90
```

Fixed constant, not per-instance state. Move to `const.py` as `TRANSIT_GRACE_SECONDS = 90`, or at minimum make it a class constant `_TRANSIT_GRACE: int = 90`.

---

## 10. Low: `CONF_OVERRIDE_DURATION_ENTITY` not editable post-setup

**`config_flow.py:87–89`, `__init__.py:322`**

Saved to `entry.data` (initial setup only), not surfaced in the options flow. Users who want to change it must delete and re-add the integration. Either move it to options, or remove it — the integer-based override duration covers the same need and is editable.

---

## 11. Low: No config entry migration step

**`config_flow.py:68`**

`VERSION = 1` with no `async_migrate_entry` handler. If the schema ever needs a breaking change, existing installs fail on load with no recovery path. Add a stub migration handler now, while the schema is still at v1.

---

## 12. Minor: `ws_save_rules` accepts unvalidated rule content

**`panel.py:143–148`**

The Voluptuous schema only asserts `rules` is a `list`. Malformed rules are silently stored and surface as `KeyError`/`TypeError` during evaluation. A deeper schema or structural sanity check would make failures loud at save time.

---

## Strengths worth preserving

- **`logic.py` HA isolation** is exactly right. The boundary is clean; tests run without HA.
- **Three-pass evaluation semantics** (priority → mode → fallback with single-pass-claims) are simple and powerful.
- **`_eval_lock`** prevents re-entrant evaluation.
- **`_opt()` helper** — options → data → default chain is clean.
- **`fill_targets` `break` after first matching rule** — first-match-wins per group is clearly expressed.
- **Test coverage** of logic.py is solid. Override test fixtures with mocked HA state are well-structured.

---

## Priority fix order

| # | Finding | Action |
|---|---------|--------|
| 1 | normalize_groups dead / format mismatch | Decide canonical format; align fill_targets or calling code |
| 2 | Armed listener not reinstated | One-liner in `_async_options_updated` |
| 3 | Tilt task leaks on unload | Track + cancel in `unload()` |
| 4 | Naive datetime | Replace with `dt_util.now()` |
| 5 | Resolver rebuilt every eval | Cache + invalidate |
| 6–12 | Encapsulation, debug code, constants, config | Clean-up pass |

---

## Amendments from Gemini review (agreed)

The following findings from Gemini's audit were not in the original report above and are valid.

### A. High: Custom variable state changes don't trigger re-evaluation

**`__init__.py:async_init`, `_build_custom_resolvers`**

`async_init` subscribes to `sun.sun`, `mode_entity`, and `armed_entity`. Custom vars bound via `CONF_CUSTOM_VARS` (e.g. `lux=sensor.outdoor_illuminance`) get no listener. Changes to those sensors only surface at the next 15-minute poll or incidental sun update. For rules that react to presence sensors or illuminance thresholds, this breaks real-time responsiveness.

Fix: after parsing `CONF_CUSTOM_VARS`, subscribe to state changes for entity-based bindings with `async_track_state_change_event`, and use `async_track_template_result` for template bindings. Re-subscribe on options change (same pattern as `reinit_mode_listener`).

### B. Medium: Positionless covers silently never commanded

**`__init__.py:480`**

```python
needs_pos = target_pos is not None and cur_pos is not None and abs(int(cur_pos) - target_pos) > tolerance
```

If `cur_pos is None` (cover reports no `current_position` attribute — common for relay-based covers or briefly-unavailable devices), `needs_pos` is always `False`. The cover is tracked in `_last_commanded` but never commanded. Silent failure with no log.

Fix: if `cur_pos is None` and `target_pos is not None`, send the command unconditionally (unknown position = assume move needed). Log a debug message when this path fires.

### C. Bug: Midnight time crossing is silently skipped

**`logic.py:62–66`**

The `=^` (rising crossing) check uses `prev < expected <= cur`. When time wraps midnight (e.g. `prev=2350`, `cur=10`, `expected=0`), `2350 < 0` is `False` so the crossing is missed. Any rule that triggers on crossing a time threshold near or at midnight will silently fail to fire.

Fix: add wrap detection in the time crossing branch:

```python
if op_str != "=v":
    wrapped = cur < prev  # midnight wrap occurred
    if wrapped:
        fires = prev < expected or expected <= cur
    else:
        fires = prev < expected <= cur
    if not fires:
        return False
```

### D. Amplification of finding #3: tilt task also sends stale commands

**`__init__.py:502–506`**

Beyond the unload leak already noted, a second failure mode exists: if conditions change or a manual override is detected during the 30 s sleep, the task fires with the original (now-wrong) tilt target. The cover moves to the correct position from the new evaluation, then jolts to an incorrect tilt 30 seconds later.

Fix: track one task per cover (not one global task), cancel before issuing a new tilt command for that cover.

```python
self._pending_tilts: dict[str, asyncio.Task] = {}

# before scheduling a tilt for entity_id:
t = self._pending_tilts.get(entity_id)
if t and not t.done():
    t.cancel()

# in unload():
for t in self._pending_tilts.values():
    if not t.done():
        t.cancel()
```

---

## Disagreements with Gemini

### 1. `_TRANSIT_GRACE` should not be user-configurable

Gemini recommends exposing `_TRANSIT_GRACE` in `config_flow.py` as an advanced option. Disagree. Transit grace is an implementation detail of override detection, not a user-facing concept. Exposing it forces users to understand the internal timing model to tune it. The right fix is promoting it from an instance attribute to a module-level constant in `const.py` (as noted in finding #9). If per-cover travel time matters in the future, it should be derived from observed command-completion deltas, not a global config knob.

### 2. "Blind covers" severity is not Critical

Gemini labels positionless covers as Critical. The integration targets modern motorized covers (Somfy, etc.) that universally report `current_position`. Positionless relay-based covers are outside the design envelope. The failure is real and worth fixing (Medium), but it doesn't threaten the reliability of the intended use case.

### 3. Crossing logic refactor is not warranted

Gemini flags the crossing operator logic as "repetitive" and suggests refactoring for clarity. The current code is correct (outside the midnight bug), well-commented, and handles three meaningfully different cases (time, string/boolean, numeric). Refactoring it into a single abstraction would obscure those distinctions. Fix the midnight bug; leave the structure alone.
