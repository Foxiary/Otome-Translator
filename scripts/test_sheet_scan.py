#!/usr/bin/env python3
"""Build a temporary workbook and confirm the scanners only read it."""
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def xml(text):
    return text.encode()


def workbook(path, translation):
    shared = ["Source", "Hello", translation]
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3">'
        + "".join(f"<si><t>{item}</t></si>" for item in shared)
        + "</sst>"
    )
    cell_c = '<c r="C2" t="s"><v>2</v></c>' if translation else ""
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>0</v></c><c r="C1" t="s"><v>0</v></c></row>
<row r="2"><c r="A2"><v>24</v></c><c r="B2" t="s"><v>1</v></c>{cell_c}</row>
</sheetData></worksheet>'''
    files = {
        "[Content_Types].xml": xml('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'),
        "_rels/.rels": xml('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": xml('<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Dialogue" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": xml('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'),
        "xl/sharedStrings.xml": shared_xml.encode(),
        "xl/worksheets/sheet1.xml": sheet.encode(),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)


def openpyxl_style(path, rows):
    """A workbook laid out the way openpyxl (and so mksheet.py) saves one: text kept
    inline in each cell, and the worksheet named from the package root."""
    def cell(ref, value):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>' if value else ""
    body = "".join(f'<row r="{i}">' + "".join(cell(f"{col}{i}", v) for col, v in zip("ABC", row)) + "</row>"
                   for i, row in enumerate(rows, 1))
    files = {
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="100" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload.encode())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    with tempfile.TemporaryDirectory() as folder:
        empty = Path(folder) / "empty.xlsx"
        workbook(empty, "")
        before = digest(empty)
        scan = subprocess.run([sys.executable, str(ROOT / "src" / "sheet_scan.py"), str(empty)], capture_output=True, text=True)
        assert digest(empty) == before, "empty-cell scan wrote the workbook"
        assert scan.returncode == 2, scan.stderr
        found = json.loads(scan.stdout.strip().splitlines()[-1])
        assert found == {"sheet": "Dialogue", "row": 2, "source": "Hello"}, found

        # A sheet mksheet.py wrote: its inline text is read, not taken for empty cells.
        made = Path(folder) / "made.xlsx"
        openpyxl_style(made, [("ID", "EN", "VI"), ("5___1A0_title", "KEY@Act 1: Death", ""), ("6___1B0_text", "Done", "Xong")])
        scan = subprocess.run([sys.executable, str(ROOT / "src" / "sheet_scan.py"), str(made)], capture_output=True, text=True)
        assert scan.returncode == 2, scan.stderr
        assert json.loads(scan.stdout.strip()) == {"sheet": "100", "row": 2, "source": "KEY@Act 1: Death"}, scan.stdout
        keys = subprocess.run([sys.executable, str(ROOT / "src" / "title_keys.py"), str(made)], capture_output=True, text=True)
        assert json.loads(keys.stdout) == {"titles": 1, "keyed": 1}, keys.stdout + keys.stderr
        openpyxl_style(made, [("ID", "EN", "VI"), ("5___1A0_title", "Act 1: Death", "")])
        keys = subprocess.run([sys.executable, str(ROOT / "src" / "title_keys.py"), str(made)], capture_output=True, text=True)
        assert json.loads(keys.stdout) == {"titles": 1, "keyed": 0}, keys.stdout + keys.stderr

        long = Path(folder) / "long.xlsx"
        workbook(long, "this translation is too long for the box")
        boxes = Path(folder) / "boxes.json"
        boxes.write_text(json.dumps([{"sheet": "Dialogue", "row": 2, "maxChars": 8}]), encoding="utf-8")
        bundle = Path(folder) / "scene.bundle"
        bundle.write_bytes(b"bundle-bytes")
        before_book, before_bundle, before_boxes = digest(long), digest(bundle), digest(boxes)
        fit = subprocess.run(
            [sys.executable, str(ROOT / "engines" / "unity" / "tools" / "sheetfit.py"), str(long), str(boxes), str(bundle)],
            capture_output=True, text=True)
        assert digest(long) == before_book
        assert digest(bundle) == before_bundle
        assert digest(boxes) == before_boxes
        assert fit.returncode == 2, fit.stderr
        overflow = json.loads(fit.stdout.strip())
        assert overflow["row"] == 2 and overflow["kind"] == "overflow"
    print("sheet scanners passed")


if __name__ == "__main__":
    main()
