#!/usr/bin/env python3
"""Worksheet names of an .xlsx workbook, in workbook order, as JSON. Only reads it.

    python sheet_names.py <workbook.xlsx>
"""
import json
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sheet_names(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
    return [sheet.attrib.get("name", "") for sheet in root.findall(".//m:sheets/m:sheet", NS)]


if __name__ == "__main__":
    sys.stdout.buffer.write(json.dumps(sheet_names(sys.argv[1]), ensure_ascii=False).encode("utf-8"))
