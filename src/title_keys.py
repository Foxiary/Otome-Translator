#!/usr/bin/env python3
"""Count chapter-title rows whose game text carries a `<japanese key>@` prefix. Only reads.

filltitles.py composes such titles from translated chapter labels. A game whose
titles carry no key - the Virche Evermore fan disc is one - has nothing for it
to compose, so the patch page skips that step instead of asking for labels.
The sheet stands in for the game: its rows are the scripts' own text, and a
title row is one whose id ends in `_title`.

    python title_keys.py <workbook.xlsx>      -> {"titles": N, "keyed": M}
"""
import json
import sys
import xml.etree.ElementTree as ET
import zipfile

from sheet_scan import NS, cell_text, column_row, shared_strings, sheet_targets


def title_keys(path):
    titles = keyed = 0
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        for _name, target in sheet_targets(archive):
            root = ET.fromstring(archive.read(target))
            rows = {}
            for cell in root.findall(".//m:c", NS):
                column, row = column_row(cell.attrib.get("r", ""))
                if column in ("A", "B"):
                    rows.setdefault(row, {})[column] = cell_text(cell, strings).strip()
            for columns in rows.values():
                if columns.get("A", "").endswith("_title"):
                    titles += 1
                    keyed += "@" in columns.get("B", "")
    return {"titles": titles, "keyed": keyed}


if __name__ == "__main__":
    print(json.dumps(title_keys(sys.argv[1])))
