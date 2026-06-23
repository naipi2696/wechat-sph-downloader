#!/usr/bin/env python3
"""WeChat SPH download - unified script for both Telegram and Weixin clients."""
import subprocess
import sys
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UNIFIED_SCRIPT = os.path.join(SCRIPT_DIR, "wechat_unified_download.py")
PYTHON311 = r"C:\Users\yy\AppData\Local\Programs\Python\Python311\python.exe"

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python wechat_unified_download.py <sph_id_or_url1> [sph_id_or_url2] ...")
        return
    
    sph_ids = []
    for arg in args:
        m = re.search(r'/sph/([A-Za-z0-9]+)', arg)
        if m:
            sph_ids.append(m.group(1))
        elif re.match(r'^[A-Za-z0-9]+$', arg):
            sph_ids.append(arg)
        else:
            sph_ids.append(arg)
    
    result = subprocess.run(
        [PYTHON311, UNIFIED_SCRIPT] + sph_ids,
        stdout=sys.stdout,
        stderr=subprocess.DEVNULL,
        cwd=SCRIPT_DIR
    )
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
