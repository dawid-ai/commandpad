"""Signal monitor — prints the exact signal the pad emits for every control.

Run it, then press each key, turn each knob, and click each knob. Whatever it
prints is the value to put in the `controls` map of profiles.json.

    python scripts/show_signals.py

Ctrl+C to quit. If a control prints NOTHING, it isn't emitting a normal
keyboard key (it may be a mouse button or a media key) — tell me and we'll
handle that case.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.platform_impl.windows import WindowsKeyListener

print("Monitoring pad signals. Press keys, turn + click both knobs.")
print("Read off the signal next to each control. Ctrl+C to quit.\n")

WindowsKeyListener().start(lambda sig: print(f"  signal -> {sig}"))

try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\ndone")
