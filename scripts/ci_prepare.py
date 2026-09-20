#!/usr/bin/env python3
"""Prepare only the disposable Ubuntu CI host for OpenSearch."""
import subprocess
import sys

if sys.platform != "linux":
    raise SystemExit("ci_prepare.py is only for the disposable Linux CI host")
subprocess.run(["sudo", "sysctl", "-w", "vm.max_map_count=262144"], check=True)
