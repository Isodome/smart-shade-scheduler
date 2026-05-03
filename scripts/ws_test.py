#!/usr/bin/env python3
"""Smoke-test the smart_shades WebSocket API against a live HA instance.

Usage:
    python3 scripts/ws_test.py --host homeassistant.local --token YOUR_TOKEN

If --token is omitted the script looks for HA_TOKEN in the environment.
"""

import argparse
import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    sys.exit("Missing dependency: pip install websockets")


async def run(host: str, token: str) -> None:
    url = f"ws://{host}:8123/api/websocket"
    print(f"Connecting to {url} …")

    async with websockets.connect(url) as ws:
        # --- auth handshake ---
        msg = json.loads(await ws.recv())
        assert msg["type"] == "auth_required", f"Unexpected: {msg}"

        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        msg = json.loads(await ws.recv())
        if msg["type"] != "auth_ok":
            sys.exit(f"Auth failed: {msg}")
        print(f"Authenticated (HA {msg.get('ha_version', '?')})\n")

        # --- smart_shades/get_config ---
        await ws.send(json.dumps({"id": 1, "type": "smart_shades/get_config"}))
        msg = json.loads(await ws.recv())

        if not msg.get("success"):
            print(f"FAIL  smart_shades/get_config → {msg.get('error')}")
            print("\nLikely causes:")
            print("  • Integration not loaded (check HA logs)")
            print("  • WebSocket command not registered (panel.py setup failed)")
            return

        result = msg["result"]
        print("OK    smart_shades/get_config")
        print(f"      entry_id     : {result.get('entry_id')}")
        print(f"      mode_entity  : {result.get('mode_entity')}")
        print(f"      current_mode : {result.get('current_mode')}")
        print(f"      mode_options : {result.get('mode_options')}")
        print(f"      rules        : {len(result.get('rules', []))} rule(s)")
        print(f"      overrides    : {result.get('overrides')}")
        if result.get("orphaned_modes"):
            print(f"      orphaned     : {result.get('orphaned_modes')}")

        rules = result.get("rules", [])
        if not rules:
            print("\nWARN  No rules stored — was the config imported?")
        else:
            modes = {}
            for r in rules:
                modes.setdefault(r.get("mode"), 0)
                modes[r["mode"]] += 1
            print("\n      Rules per mode:")
            for mode, count in modes.items():
                print(f"        {mode}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Shades WS smoke test")
    parser.add_argument("--host", default=os.getenv("HA_HOST", "homeassistant.local"))
    parser.add_argument("--token", default=os.getenv("HA_TOKEN"))
    args = parser.parse_args()

    if not args.token:
        sys.exit("Provide --token or set HA_TOKEN env var")

    asyncio.run(run(args.host, args.token))


if __name__ == "__main__":
    main()
