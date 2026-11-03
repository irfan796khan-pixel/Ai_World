"""Used by run_girl_room.bat.  python wait_for.py URL SECONDS  -> waits until URL answers.
Exit code 0 = it answers, 1 = it did not answer in time."""
import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1]
wait = float(sys.argv[2]) if len(sys.argv) > 2 else 0
end = time.time() + wait
while True:
    try:
        urllib.request.urlopen(url, timeout=2)
        sys.exit(0)
    except urllib.error.HTTPError:
        sys.exit(0)          # it answered (even with an error code): the server is up
    except Exception:
        if time.time() >= end:
            sys.exit(1)
        time.sleep(1)
