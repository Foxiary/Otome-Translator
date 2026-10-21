#!/usr/bin/env python3
"""The engine's width check takes box widths from windows.json in the project folder, and nowhere else."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'engines' / 'otomate' / 'tools'
PROBE = '''
import json, sys
sys.path.insert(0, sys.argv[1])
import textwidth as t
print(json.dumps({"ceiling": t.CEILING, "framed": t.ceiling_for(t.WINDOW_FRAMED),
                  "dialogue": t.ceiling_for(t.WINDOW_DIALOGUE), "default": t.ceiling_for(None),
                  "measured": t.MEASURED, "source": t.ceilings_source()}))
'''


def probe(folder):
    out = subprocess.run([sys.executable, '-c', PROBE, str(TOOLS)], cwd=folder, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def main():
    with tempfile.TemporaryDirectory() as folder:
        # No windows.json: no box width at all, not some other game's.
        bare = probe(folder)
        assert bare['ceiling'] is None and bare['framed'] is None and bare['default'] is None, bare
        assert bare['measured'] == {} and 'chua do khung chu' in bare['source'], bare

        windows = Path(folder) / 'windows.json'
        windows.write_text(json.dumps({'windows': {'framed': {'ceiling': 2174}, 'backlog': {'ceiling': 2400.4}}}), encoding='utf-8')
        measured = probe(folder)
        assert measured['ceiling'] == 2400, measured
        assert measured['default'] == 2400, measured          # ceiling_for's default follows the backlog
        assert measured['framed'] == 2174, measured           # narrower than the backlog, so it binds
        assert measured['dialogue'] == 2400, measured          # unmeasured, held to the backlog

        # Only a window measured: it binds, everything else has no ceiling.
        windows.write_text(json.dumps({'windows': {'framed': {'ceiling': 2069}}}), encoding='utf-8')
        framed_only = probe(folder)
        assert framed_only['framed'] == 2069 and framed_only['default'] is None, framed_only
        assert 'windows.json' in measured['source'] and 'framed 2174' in measured['source'], measured

        # A measured dialogue box narrower than the backlog binds that window only.
        windows.write_text(json.dumps({'windows': {'dialogue': {'ceiling': 2300}}}), encoding='utf-8')
        narrow = probe(folder)
        assert narrow['dialogue'] == 2300 and narrow['default'] is None, narrow

        # A broken or odd file changes nothing.
        for text in ('{not json', '[]', json.dumps({'windows': {'framed': {'ceiling': 'wide'}, 'backlog': {'ceiling': True}}})):
            windows.write_text(text, encoding='utf-8')
            assert probe(folder)['measured'] == {}, text
    print('textwidth windows.json assertions passed')


if __name__ == '__main__':
    main()
