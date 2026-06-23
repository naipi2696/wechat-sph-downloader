#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check links from a saved file and download any WeChat sph videos that aren't already downloaded."""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UNIFIED_SCRIPT = os.path.join(SCRIPT_DIR, "wechat_unified_download.py")
PYTHON311 = r"C:\Users\yy\AppData\Local\Programs\Python\Python311\python.exe"
LINKS_FILE = Path(r"E:\Hermes\wechat_sph_links.txt")


def main():
    if not LINKS_FILE.exists():
        print("No links file found at", LINKS_FILE)
        return

    links = [l.strip() for l in LINKS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not links:
        print("Links file is empty")
        return

    # Extract sph_ids from links
    sph_ids = []
    for link in links:
        m = re.search(r'/sph/([A-Za-z0-9]+)', link)
        if m:
            sph_ids.append(m.group(1))

    if not sph_ids:
        print("No valid sph IDs found in links file")
        return

    # Call unified download script
    result = subprocess.run(
        [PYTHON311, UNIFIED_SCRIPT] + sph_ids,
        stdout=sys.stdout,
        stderr=subprocess.DEVNULL,
        cwd=SCRIPT_DIR
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
