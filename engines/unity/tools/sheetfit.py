#!/usr/bin/env python3
"""Read-only check: flag a translation that is longer than its text box allows.

Reads the workbook and the box table. Does not write either file, or the bundle
path when one is given.
"""
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
    return ["".join(node.text or "" for node in item.iter(MAIN + "t")) for item in root.findall("m:si", NS)]


def rows_of(path):
    found = []
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib.get("Id"): rel.attrib.get("Target") for rel in relationships}
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            relation = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = targets[relation]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            name = sheet.attrib.get("name") or "Sheet"
            root = ET.fromstring(archive.read(target))
            by_row = {}
            for cell in root.findall(".//m:c", NS):
                column, row = column_row(cell.attrib.get("r", ""))
                value = cell.find("m:v", NS)
                text = ""
                if value is not None and value.text is not None:
                    text = strings[int(value.text)] if cell.attrib.get("t") == "s" else value.text
                by_row.setdefault(row, {})[column] = text
            for row, columns in by_row.items():
                found.append({"sheet": name, "row": row, "translation": columns.get("C", "")})
    return found


def main():
    workbook, boxes_path = sys.argv[1], sys.argv[2]
    bundle = sys.argv[3] if len(sys.argv) > 3 else None
    if bundle:
        with open(bundle, "rb") as handle:
            handle.read()
    boxes = json.loads(open(boxes_path, encoding="utf-8").read())
    limits = {(item["sheet"], int(item["row"])): int(item["maxChars"]) for item in boxes}
    reported = []
    for row in rows_of(workbook):
        limit = limits.get((row["sheet"], row["row"]))
        if limit is not None and len(row["translation"]) > limit:
            reported.append({"sheet": row["sheet"], "row": row["row"], "kind": "overflow"})
    for item in reported:
        print(json.dumps(item))
    sys.exit(2 if reported else 0)


if __name__ == "__main__":
    main()
