#!/usr/bin/env python3
"""cleanup_broker_queues.py — Delete stale SAM event-mesh-gw queues via SEMP v2.

Each SAM restart creates new durable queues with unique UUID suffixes.
Old ones accumulate and eventually hit the broker's 100-endpoint license limit,
preventing startup. This script deletes queues matching 'gdk/event-mesh-gw'
or 'gdk/viz'.

Non-fatal if the broker is unreachable (called conditionally from common.sh).
"""

import base64
import json
import urllib.parse
import urllib.request

BROKER_URL = "http://localhost:8080"
CREDS = base64.b64encode(b"admin:admin").decode()


def semp(path, method="GET"):
    req = urllib.request.Request(f"{BROKER_URL}/SEMP/v2/{path}", method=method)
    req.add_header("Authorization", f"Basic {CREDS}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def main():
    queues = semp("monitor/msgVpns/default/queues?count=200").get("data", [])
    deleted = 0
    for q in queues:
        name = q.get("queueName")
        if not name:
            continue
        if "gdk/event-mesh-gw" in name or "gdk/viz" in name:
            semp(
                f"config/msgVpns/default/queues/{urllib.parse.quote(name, safe='')}",
                "DELETE",
            )
            deleted += 1
    if deleted:
        print(f"  🧹 Deleted {deleted} stale broker queue(s)")


if __name__ == "__main__":
    main()
