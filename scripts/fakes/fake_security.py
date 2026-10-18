#!/usr/bin/env python3
"""A fake macOS `security` for the offline tests (set ALERT_SECURITY_BIN to this file). Knows find-generic-password (-a ACCOUNT -s SERVICE [-w]) and delete-generic-password.
The "keychain" is the JSON file FAKE_KEYCHAIN ({service: value}); every call's arguments (never a value) are appended to FAKE_KEYCHAIN_LOG. Exit code 44 = item not found, like the real one."""
import json
import os
import sys

args = sys.argv[1:]
store = json.load(open(os.environ["FAKE_KEYCHAIN"]))
with open(os.environ["FAKE_KEYCHAIN_LOG"], "a") as fh:
    fh.write(" ".join(args) + "\n")
if not args or args[0] not in ("find-generic-password", "delete-generic-password"):
    sys.exit(1)
svc = args[args.index("-s") + 1] if "-s" in args else None
if svc not in store:
    sys.exit(44)
if args[0] == "delete-generic-password":
    sys.exit(0)
if "-w" in args:
    print(store[svc])
else:
    print(f'keychain: "login"\nattributes:\n    "svce"<blob>="{svc}"')
