# Smart Shade Scheduler - Architectural Audit Report

## 1. Executive Summary
The Python engine of the `smart_shades` integration demonstrates a mature, robust, and highly modular architecture. The separation between Home Assistant integration logic (`__init__.py`) and pure rule evaluation (`logic.py`) is an excellent design choice that promotes testability and maintainability. The state machine successfully handles the complexities of real-world cover behavior, including manual override detection and hardware-specific delays.

However, the audit revealed several critical and moderate issues related to event reactivity, state handling for positionless covers, and asynchronous task management. These vulnerabilities must be addressed to ensure enterprise-grade reliability and real-time responsiveness.

## 2. Architectural Strengths
- **Decoupled Rule Engine:** `logic.py` is cleanly separated from Home Assistant's core imports. By accepting generic dictionaries (`vals`, `prev_vals`) to evaluate conditions, the engine is 100% unit-testable, entirely synchronous, and performant.
- **Fail-Safe Variable Resolution:** Missing variables naturally fail safely instead of crashing the evaluation pipeline. Returning `False` when a sensor is missing ensures forward compatibility and robustness against unavailable devices.
- **Intelligent Override Management:** The integration elegantly handles manual interventions. By utilizing a configurable `tolerance` and a `_TRANSIT_GRACE` period (90s), the system accurately distinguishes between a user manually adjusting a cover and the cover simply taking time to reach its automated target.
- **Hardware-Aware Tilt Sequencing:** The `tilt_delay` mechanism acknowledges a common limitation in external venetian blinds (raffstores), where tilt commands must be delayed until the vertical drop is complete.

## 3. Critical Vulnerabilities & Bugs

### A. Missing Event Listeners for Custom Variables
- **Location:** `__init__.py` -> `async_init()` & `_build_custom_resolvers()`
- **Issue:** The integration allows users to bind custom variables via `CONF_CUSTOM_VARS` (e.g., `lux=sensor.outdoor_illuminance` or templates). However, the manager only subscribes to state changes for `sun.sun`, `mode_entity`, and `armed_entity`.
- **Impact:** Changes to custom sensors will **not** immediately trigger a rule evaluation. The engine only notices these changes during the fallback 15-minute polling interval or if an unrelated entity (like the sun) changes state. This severely breaks real-time responsiveness for custom triggers.

### B. "Blind" Covers Silently Ignored
- **Location:** `__init__.py` -> `_do_evaluate()`
- **Issue:** The condition `needs_pos = target_pos is not None and cur_pos is not None and abs(...) > tolerance` strictly requires `cur_pos` to be populated. If a cover does not report a `current_position` attribute (common for simple relay-based covers) or is briefly unavailable at startup, `cur_pos` evaluates to `None`.
- **Impact:** The `needs_pos` flag evaluates to `False`, and the integration will never send a position command to that cover, silently failing to automate it.

### C. Stale Tilt Commands (Race Condition in Delay Queue)
- **Location:** `__init__.py` -> `_delayed_tilts()`
- **Issue:** The `tilt_delay` is implemented using a fire-and-forget `asyncio.sleep()` task. If conditions change or a manual override occurs during this sleep period, the task is not cancelled and will still execute with the original (now stale) tilt target.
- **Impact:** A shade might correctly move to a new position but abruptly tilt to an incorrect angle 30 seconds later, overriding newer commands and confusing the user.

## 4. Code Quality & Code Smells
- **Hardcoded Transit Grace Period:** `_TRANSIT_GRACE = 90` is hardcoded. While 90 seconds is a safe upper bound, massive awnings might take up to 2 minutes, whereas indoor roller blinds finish in 10 seconds. This static value limits flexibility.
- **Midnight Time Crossing Edge-Case:** In `logic.py`, monotonic crossing logic (`prev < expected <= cur`) is used for time. Because time wraps from 2359 to 0000 at midnight, an `=^` crossing check precisely at midnight will evaluate to `False` (`2359 < 0 <= 0` is `False`).
- **Repetitive Crossing Logic:** The crossing operators (`=^`, `=v`, `=`) in `logic.py` contain slightly nested and repetitive boolean logic. While it works reliably (outside the midnight wrap), it could be refactored for clarity.

## 5. Architectural Recommendations

1. **Implement Dynamic Event Tracking (High Priority):**
   - Parse `CONF_CUSTOM_VARS` during initialization.
   - Use `async_track_state_change_event` for simple entity mappings.
   - Use `async_track_template_result` for template mappings.
   - Ensure these listeners are cleaned up and re-initialized when options are updated.

2. **Add Fallback for Positionless Covers (High Priority):**
   - Modify the `needs_pos` check to account for covers lacking `current_position`. If `cur_pos is None`, fall back to checking the cover's generic `state` (e.g., `open`, `closed`), or simply allow the command to be sent on state transitions.

3. **Implement Task Cancellation for Delayed Tilts (Medium Priority):**
   - Maintain a dictionary mapping `entity_id` to its active `asyncio.Task` for delayed tilts.
   - Before evaluating rules or issuing new commands for a cover, cleanly cancel any pending tilt task.

4. **Expose Advanced Timers to Configuration (Low Priority):**
   - Move `_TRANSIT_GRACE` to `config_flow.py` as an advanced option to allow user tuning.

5. **Refine Time Wrap Logic (Low Priority):**
   - Update `logic.py` to handle modulo arithmetic when evaluating time crossings, ensuring that day boundary crossings trigger reliably.

## 6. Additional Findings (Amended from Claude's Audit)
*Upon reviewing an independent audit by Claude, the following valid findings have been incorporated into this report:*

- **Armed Listener Not Reinstated on Options Change (High):** `_async_options_updated` correctly reinitializes the mode listener but forgets to call `_reinit_armed_listener()`. If a user changes the armed entity via the options UI, the engine will stop reacting to the new armed entity's state changes until HA is restarted.
- **Tilt Delay Task Leaks on Unload (High):** When the integration is unloaded, any sleeping `_delayed_tilts` task continues to run in the background. It will wake up and execute against an unloaded manager. The pending task must be stored and explicitly cancelled in the `unload()` method.
- **Naive Datetime is Timezone Unsafe (Medium):** The engine uses `datetime.now()` to get the current time. In Home Assistant's Docker environment, this often defaults to UTC rather than the user's configured local timezone. This should be replaced with Home Assistant's timezone-aware `homeassistant.util.dt.now()`.
- **Custom Resolvers Rebuilt Every Cycle (Medium):** `_build_custom_resolvers()` parses strings and builds functions on every single evaluation cycle. This should be cached and only invalidated when options are updated.
- **Evaluation Task Pile-up (Medium):** All event callbacks spawn a new `async_evaluate_rules()` task. While protected by a lock, rapid concurrent events (e.g., sun change + mode change) will queue multiple identical evaluation tasks back-to-back. Implementing a debounce or checking for a pending task would be much more efficient.
- **Dead Code / Unused Function (Low):** `normalize_groups` is defined in `logic.py` but never actually called during rule evaluation, and its expected output structure doesn't match what the engine actually consumes. It should be removed or properly integrated if a schema migration is planned.
- **Private Attributes Read Cross-Class (Low):** Components like `sensor.py` access private attributes like `_last_commanded` directly from `ShadeManager`. Exposing these via public properties `@property` would fix this encapsulation break.

## 7. Disputed Findings
*The following findings from Claude's audit were reviewed but are not recommended for implementation:*

- **Adding a Stub Migration Handler for v1 Config (Claude #11):** Claude suggests adding an `async_migrate_entry` stub while the schema is still at `VERSION = 1`. **Disagreement:** This is an anti-pattern in Home Assistant. You should only implement a migration handler when you actually bump the version to v2. Adding a stub for v1 adds unnecessary boilerplate and serves no functional purpose.
- **Moving `_TRANSIT_GRACE` to `const.py` (Claude #9):** Claude argues that `self._TRANSIT_GRACE = 90` is a fixed constant and should be moved out of the class instance. **Disagreement:** As highlighted in my own recommendations, this value should ideally be user-configurable since different shades have drastically different transit times. Keeping it as an instance attribute (`self._TRANSIT_GRACE`) is the correct architectural foundation for eventually replacing it with a per-entry configuration lookup (`self._opt('transit_grace', 90)`) without breaking encapsulation.
