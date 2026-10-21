#!/usr/bin/env python3
"""Where the Japanese build's archives are in the project folder, as the engine finds them.

Run from the project folder. Prints {name: path or null} as JSON, using the
engine's own tools/jpfiles.py so the app reports what the tools will read.

    python find_jp.py STORY.cpk SYSTEM.cpk
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from jpfiles import find_jp  # noqa: E402

print(json.dumps({name: find_jp(name) for name in sys.argv[1:]}))
