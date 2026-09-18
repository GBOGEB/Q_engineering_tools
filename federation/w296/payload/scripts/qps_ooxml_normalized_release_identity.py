#!/usr/bin/env python3
"""Compute a governed normalized release identity for OOXML packages.

Raw binary SHA-256 remains the exact-byte identity. This normalized digest is a
separate release-equivalence identity that removes known volatile OOXML metadata
while retaining all document/workbook content, relationships, styles and package
structure. It MUST NOT be used to claim byte identity.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

VOLATILE_PARTS = {"docProps/core.xml"}
VOLATILE_CORE_TAGS = {
    "{http://purl.org/dc/terms/}created",
    "{http://purl.org/dc/terms/}modified",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}revision",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_xml(name: str, data: bytes) -> bytes:
    if name == "docProps/core.xml":
        root = ET.fromstring(data)
        for child in list(root):
            if child.tag in VOLATILE_CORE_TAGS:
                root.remove(child)
        data = ET.tostring(root, encoding="utf-8", xml_declaration=False)
    try:
        text = data.decode("utf-8")
        out = io.StringIO()
        ET.canonicalize(xml_data=text, out=out, with_comments=False)
        return out.getvalue().encode("utf-8")
    except (UnicodeDecodeError, ET.ParseError):
        return data


def normalized_manifest(path: Path) -> dict:
    rows = []
    with zipfile.ZipFile(path, "r") as zf:
        names = sorted(n for n in zf.namelist() if not n.endswith("/"))
        for name in names:
            data = zf.read(name)
            if name.endswith(".xml") or name.endswith(".rels"):
                data = normalize_xml(name, data)
            rows.append({"part": name, "normalized_sha256": sha256_bytes(data), "size": len(data)})
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "raw_sha256": raw_sha256(path),
        "normalized_release_sha256": sha256_bytes(canonical),
        "part_count": len(rows),
        "parts": rows,
        "identity_semantics": "NORMALIZED_RELEASE_EQUIVALENCE_NOT_RAW_BYTE_IDENTITY",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    result = {str(p): normalized_manifest(p) for p in args.paths}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
