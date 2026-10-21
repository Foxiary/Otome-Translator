#!/usr/bin/env python3
"""Report empty translation cells in column C, with the source text from column B.

This script only reads the workbook."""
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def column_row(ref):
    column = "".join(char for char in ref if char.isalpha())
    row = int("".join(char for char in ref if char.isdigit()) or "0")
    return column, row


def shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("m:si", NS):
        values.append("".join(node.text or "" for node in item.iter(MAIN + "t")))
    return values


def sheet_targets(archive):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.attrib.get("Id"): rel.attrib.get("Target") for rel in relationships}
    found = []
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        relation = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = targets[relation]
        # Excel writes targets relative to xl/ ("worksheets/sheet1.xml"); openpyxl,
        # which mksheet.py saves with, writes them from the package root
        # ("/xl/worksheets/sheet1.xml").
        if target.startswith("/"):
            target = target.lstrip("/")
        elif not target.startswith("xl/"):
            target = "xl/" + target
        found.append((sheet.attrib.get("name") or "Sheet", target))
    return found


def cell_text(cell, strings):
    # openpyxl, which mksheet.py saves with, keeps text in the cell itself rather
    # than in the shared strings table; read that or every such cell looks empty.
    if cell.attrib.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(MAIN + "t"))
    value = cell.find("m:v", NS)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return strings[int(value.text)]
    return value.text


def findings(path):
    reported = []
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        for name, target in sheet_targets(archive):
            root = ET.fromstring(archive.read(target))
            rows = {}
            for cell in root.findall(".//m:c", NS):
                column, row = column_row(cell.attrib.get("r", ""))
                rows.setdefault(row, {})[column] = cell_text(cell, strings).strip()
            for row, columns in sorted(rows.items()):
                if columns.get("B") and not columns.get("C"):
                    reported.append({"sheet": name, "row": row, "source": columns["B"]})
    return reported


def main():
    path = sys.argv[1]
    for item in findings(path):
        print(json.dumps(item))
    sys.exit(2 if findings(path) else 0)


if __name__ == "__main__":
    main()
