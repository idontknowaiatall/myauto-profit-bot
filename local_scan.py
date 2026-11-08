"""
One scan cycle from a PC (Windows Task Scheduler, every ~30 min).

myauto answers home/VPN connections but blocks GitHub's servers, so the
scheduled scan runs here. Output goes to logs/local-scan.log.
Task: pythonw.exe local_scan.py, start in this folder.
"""
import datetime
import os
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))
os.environ.setdefault("MAX_PAGES", "15")

LOG = BASE / "logs" / "local-scan.log"
LOG.parent.mkdir(exist_ok=True)
if LOG.exists() and LOG.stat().st_size > 5_000_000:
    LOG.replace(LOG.with_name("local-scan.old.log"))

with open(LOG, "a", encoding="utf-8") as log:
    sys.stdout = sys.stderr = log  # pythonw has no console
    print(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===", flush=True)
    try:
        import main
        main.run_once()
    except Exception:
        traceback.print_exc()
