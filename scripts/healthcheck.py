#!/usr/bin/env python3
"""Probe all requested TCP ports; additionally verify OpenSearch HTTP readiness."""
import argparse
import json
import socket
import sys
import time
import urllib.request

PORTS = {"PostgreSQL": 5432, "FerretDB": 27017, "NATS": 4222, "OpenSearch": 9200}


def probe(host):
    errors = []
    for name, port in PORTS.items():
        try:
            with socket.create_connection((host, port), timeout=2):
                pass
        except OSError as error:
            errors.append(f"{name} {host}:{port}: {error}")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://{host}:9200/_cluster/health", timeout=3) as response:
            status = json.load(response)
        if status.get("status") not in ("yellow", "green"):
            errors.append(f"OpenSearch cluster not ready: {status.get('status')}")
    except (OSError, ValueError) as error:
        errors.append(f"OpenSearch HTTP: {error}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--wait", type=float, default=0, help="Readiness deadline in seconds")
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        errors = probe(args.host)
        if not errors:
            print(json.dumps({"ok": True, "tcp_ports": PORTS, "opensearch_http": "ready"}))
            return 0
        if time.monotonic() >= deadline:
            print(json.dumps({"ok": False, "errors": errors}), file=sys.stderr)
            return 1
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
