# Codebase Analysis: Smart Shade Scheduler (2026-05-12)

I have performed a thorough review of the Smart Shade Scheduler codebase. Below is a breakdown of architectural weaknesses, code smells, and potential maintainability issues.

## 1. JavaScript Duplication (The "Inlined" Smell)
**Files**: `www/conditions.js` and `www/smart_shades_panel.js`
*   **The Issue**: `smart_shades_panel.js` completely inlines all the parsing, validation, and string formatting logic from `conditions.js` (lines 20-106) with a comment citing *"to avoid async-import timing issues"*.
*   **Impact**: This is a classic violation of DRY (Don't Repeat Yourself). Any bug fix or feature addition to the condition parser must be duplicated manually.
*   **Recommendation**: Implement a simple bundler (like Vite, esbuild, or Rollup) to combine modules at build time, or refactor the panel initialization to properly `await` the ES module import.

## 2. The `ShadeManager` God Class
**File**: `__init__.py`
*   **The Issue**: `ShadeManager` is doing too much. It handles:
    *   Lifecycle management (listening to HA startup, intervals, sun changes).
    *   State resolution (compiling and executing Jinja templates).
    *   Core orchestrating (calling `logic.py`).
    *   Actuation (calling Home Assistant services directly in `_control_shade`).
    *   Override tracking and timeout management.
*   **Impact**: High coupling. Testing `ShadeManager` requires mocking almost the entirety of Home Assistant's state machine and service registry.
*   **Recommendation**: Split `ShadeManager` into a `TriggerController` (handles HA events), a `StateResolver` (handles variables and templates), and an `Actuator` (handles service calls and divergence detection).

## 3. Naive Concurrency & Polling
**File**: `__init__.py` (`_do_evaluate` and interval tracking)
*   **The Issue**: The system relies on a hybrid of event-driven (`sun.sun`, mode changes) and interval-based polling (every X minutes). When evaluating, it locks via `asyncio.Lock()` and recalculates *all* variables (including evaluating custom Jinja templates) for *every* rule.
*   **Impact**: If custom variables use heavy templates, evaluating them every few minutes (or rapidly upon multiple state changes) will cause unnecessary CPU load on the HA event loop.
*   **Recommendation**: Use Home Assistant's `async_track_template` for custom variables so they only trigger evaluation when their specific underlying entities change, rather than polling/evaluating them blindly.

## 4. Hardcoded Divergence Timers & Magic Numbers
**File**: `__init__.py`
*   **The Issue**: `_TRANSIT_GRACE = 90` is hardcoded. It assumes covers take at most 90 seconds to move.
*   **Impact**: If a cover takes 120 seconds to close, the script will check its position at 91 seconds, see it hasn't reached the target, assume the user manually intervened, and flag it as an "override". Conversely, if a user manually stops a fast cover at 30 seconds, the system ignores it for another 60 seconds.
*   **Recommendation**: Make transit grace time configurable, or ideally, track the cover's actual `state` (e.g., `opening`, `closing`) rather than guessing based on time.

## 5. Inconsistent Singleton Assumptions
**File**: `panel.py`
*   **The Issue**: The WebSocket command `ws_get_config` does `entry = entries[0]`. It assumes only one instance of the integration exists. However, `ws_save_rules` looks up the entry by `msg["entry_id"]`.
*   **Impact**: If a user configures two instances of the integration (e.g., for different houses or distinct mode selectors), the UI will only ever load the rules for the first one but might corrupt the other when saving.
*   **Recommendation**: Enforce a single config entry in `config_flow.py` via `_abort_if_unique_id_configured(DOMAIN)`, or pass the `entry_id` from the panel URL/state into `ws_get_config`.

## 6. Manual Cache Busting
**File**: `panel.py`
*   **The Issue**: `_JS_VERSION = "51"` is hardcoded and used to break browser caching (`?v={_JS_VERSION}`).
*   **Impact**: Developers must remember to manually increment this integer every time they modify `smart_shades_panel.js`. If forgotten, users will experience broken UIs due to stale caches.
*   **Recommendation**: Use a hash of the file's contents at runtime (or build time) to append to the URL, ensuring cache busts happen automatically.

## 7. Blind spots in `logic.py`
**File**: `logic.py`
*   **The Issue**: Crossing conditions (`=`, `=^`, `=v`) immediately fail if `prev_vals` is None. After Home Assistant restarts, the first evaluation cycle has no `prev_vals`.
*   **Impact**: If a sunrise happens while HA is restarting, the crossing condition is missed entirely.
*   **Recommendation**: The integration should persist the last known variable states to `.storage` or restore them from HA's state machine on startup to ensure continuity.
