"""
send_command.py — Send remote commands to the Ram (lock, unlock, start, etc).

Usage (PowerShell):
  $env:MOPAR_EMAIL = "you@example.com"
  $env:MOPAR_PASSWORD = "your_password"
  $env:MOPAR_PIN = "1234"
  python scripts\send_command.py lock
  python scripts\send_command.py unlock
  python scripts\send_command.py engine_on
  python scripts\send_command.py engine_off
  python scripts\send_command.py lights_horn
  python scripts\send_command.py refresh_location
"""

import os
import sys

from py_uconnect import Client, brands
from py_uconnect.command import (
    COMMAND_DOORS_LOCK,
    COMMAND_DOORS_UNLOCK,
    COMMAND_ENGINE_ON,
    COMMAND_ENGINE_OFF,
    COMMAND_LIGHTS,
    COMMAND_LIGHTS_HORN,
    COMMAND_REFRESH_LOCATION,
    COMMAND_TRUNK_LOCK,
    COMMAND_TRUNK_UNLOCK,
)

# Hardcoded — your Ram only. Edit if you want to send commands to a different vehicle.
TARGET_VIN = "3C6UR5FJ6NG305274"

CMD_MAP = {
    "lock": COMMAND_DOORS_LOCK,
    "unlock": COMMAND_DOORS_UNLOCK,
    "engine_on": COMMAND_ENGINE_ON,
    "engine_off": COMMAND_ENGINE_OFF,
    "lights": COMMAND_LIGHTS,
    "lights_horn": COMMAND_LIGHTS_HORN,
    "refresh_location": COMMAND_REFRESH_LOCATION,
    "trunk_lock": COMMAND_TRUNK_LOCK,
    "trunk_unlock": COMMAND_TRUNK_UNLOCK,
}


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <command>")
        print(f"Available: {', '.join(CMD_MAP.keys())}")
        sys.exit(1)

    cmd_name = sys.argv[1].lower()
    if cmd_name not in CMD_MAP:
        print(f"Unknown command: {cmd_name}")
        print(f"Available: {', '.join(CMD_MAP.keys())}")
        sys.exit(1)

    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")

    if not (email and password and pin):
        print("ERROR: MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN must be set")
        sys.exit(1)

    client = Client(email=email, password=password, pin=pin, brand=brands.RAM_US)
    cmd = CMD_MAP[cmd_name]

    print(f"Sending {cmd.name} to VIN {TARGET_VIN}…")
    try:
        client.command(TARGET_VIN, cmd)
        print("Command sent. Truck may take 30-60s to respond.")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
