"""Install homeassistant stubs before any test module is imported."""
import sys
import types


def _stub(name: str, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return mod


_stub("homeassistant")
_stub("homeassistant.const", EVENT_HOMEASSISTANT_STARTED="homeassistant_started")
_stub("homeassistant.core",  HomeAssistant=object, callback=lambda f: f)
_stub("homeassistant.helpers")
_stub("homeassistant.helpers.event",
      async_track_state_change_event=None,
      async_track_time_change=None,
      async_track_time_interval=None)
