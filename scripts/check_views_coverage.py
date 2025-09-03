#!/usr/bin/env python3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(xml_path: str, root: str = "backend") -> int:
    xml = ET.parse(xml_path)
    root_el = xml.getroot()
    failed: list[tuple[str, int, int]] = []
    for cls in root_el.findall(".//class"):
        filename = cls.attrib.get("filename", "")
        p = Path(filename)
        if not filename.startswith(root + "/"):
            continue
        if p.name.startswith("views") and p.suffix == ".py":
            lines = cls.find("lines")
            if lines is None:
                continue
            total = 0
            covered = 0
            for line in lines.findall("line"):
                total += 1
                hits = int(line.attrib.get("hits", "0"))
                if hits > 0:
                    covered += 1
            if total > 0 and covered < total:
                failed.append((filename, covered, total))

    if failed:
        print("Views coverage check failed (require 100%):", file=sys.stderr)
        for f, c, t in failed:
            print(f" - {f}: {c}/{t}", file=sys.stderr)
        return 1
    print("Views coverage: OK (100%)")
    return 0


if __name__ == "__main__":
    xml_path = sys.argv[1] if len(sys.argv) > 1 else "coverage.xml"
    sys.exit(main(xml_path))

