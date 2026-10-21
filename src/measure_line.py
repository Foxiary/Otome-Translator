#!/usr/bin/env python3
"""Width of one displayed line in the game's own font units, for the measure screen.

Run from the project folder. Uses the engine's own measuring code (tools/textwidth.py)
and the fonts the patch will ship, so the number matches what the width check
compares against. Only reads the fonts.

    python measure_line.py "<line as shown on screen>" [font cpk]
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from reflow import resolve_font  # noqa: E402
from textwidth import Widths, display_lines  # noqa: E402


def main():
    text = sys.argv[1]
    # Without an explicit file, prefer the built fonts and fall back to the stock ones.
    path, stock = (sys.argv[2], False) if len(sys.argv) > 2 else resolve_font(None)
    if not os.path.exists(path):
        print(json.dumps({'error': 'font', 'path': path}))
        sys.exit(1)
    lines = [line for line in display_lines(text.replace('\r', '').replace('\n', '#n')) if line.strip()]
    line = lines[0] if lines else ''
    widths = Widths.from_cpk(path)
    result = {'font': os.path.abspath(path), 'stock': stock, 'line': line, 'lines': len(lines),
              'widths': {name: widths.width(name, line) for name in sorted(widths.fonts)}}
    # UTF-8 whatever the console's code page, so Vietnamese survives the pipe.
    sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
