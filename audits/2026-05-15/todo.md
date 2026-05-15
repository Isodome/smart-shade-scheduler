# Smart Shade Scheduler - Audit Action Items

## 1. Both Agree (To Do)

- **Fix `_delayed_tilts` task management** (prevents stale tilt commands and leaks on unload)
  - [x] Work on this
  - [x] Done


- **Add dynamic event tracking for `CONF_CUSTOM_VARS`** (fixes unresponsive custom sensors)
  - [ ] Work on this
  - [ ] Done

- **Add "Clear Overrides" button to hamburger menu** (improves UX by allowing bulk override clearing from the panel)
  - [x] Work on this
  - [x] Done

- **Discount tilt delay based on travel distance** (e.g. if moving 50% distance, wait only 50% of the configured delay)
  - [x] Work on this
  - [ ] Done

- **Fix "Blind" covers bug** (add fallback for covers lacking `current_position` or `current_tilt_position` so commands aren't silently dropped)
  - [x] Work on this
  - [x] Done

- **Test coverage reports** (setup pytest-cov and generate reports)
  - [ ] Work on this
  - [ ] Done


## 2. Only Gemini (To Do)

- **Simplify repetitive crossing operator logic** (`=^`, `=v`, `=`) in `logic.py`
  - [ ] Work on this
  - [ ] Done


## 3. Only Claude (To Do)



- **Validate `ws_save_rules` payload** structurally in `panel.py` to prevent malformed saves
  - [ ] Work on this
  - [ ] Done


- **Add an `async_migrate_entry` stub** for v1 config *(Note: Gemini disputes this as an anti-pattern until v2)*
  - [ ] Work on this
  - [ ] Done

- **Move `_TRANSIT_GRACE` to `const.py`** *(Note: This was completed and exposed to user config)*
  - [x] Work on this
  - [x] Done


## 4. Completed Tasks

- **Reinstate Armed entity listener** on options change (`_async_options_updated`)
  - [x] Work on this
  - [x] Done

- **Replace naive `datetime.now()`** with timezone-aware `dt_util.now()`
  - [x] Work on this
  - [x] Done

- **Cache custom resolvers** (`_build_custom_resolvers`) instead of rebuilding on every cycle
  - [x] Work on this
  - [x] Done

- **Fix encapsulation breaks** (use `@property` for `_last_commanded` etc. instead of direct access in `sensor.py`)
  - [x] Work on this
  - [x] Done

- **Clean up `normalize_groups`** (resolve dead code / format mismatch in `logic.py`)
  - [x] Work on this
  - [x] Done

- **Fix midnight time crossing bug** (handle modulo arithmetic for time wraps in `logic.py`)
  - [x] Work on this
  - [x] Done

- **Remove debug/introspection code** (`inspect.signature`) from `panel.py`
  - [x] Work on this
  - [x] Done

- **Expose `_TRANSIT_GRACE` to user configuration** (so users with slow/fast shades can tune it)
  - [x] Work on this
  - [x] Done

- **Make `CONF_OVERRIDE_DURATION_ENTITY` editable** post-setup in options flow
  - [x] Work on this
  - [x] Done

- **Prevent evaluation task pile-up** (debounce logic with high-priority escalation)
  - [x] Work on this
  - [x] Done
