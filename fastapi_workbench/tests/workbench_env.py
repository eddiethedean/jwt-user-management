from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RealWorkbenchInfo:
    """
    Information needed to run real-workbench integration tests.
    """

    rserver_url_bin: str
    curl_bin: str


def _which(cmd: str) -> str | None:
    p = shutil.which(cmd)
    return str(p) if p else None


def detect_real_workbench() -> RealWorkbenchInfo | None:
    """
    Detect whether we can run true Workbench-proxy integration tests.

    Conditions:
    - RS_SERVER_URL is set (Workbench)
    - rserver-url binary exists at the standard path
    - curl is available (used as an HTTPS client with -k to avoid cert issues)
    """
    if not os.environ.get("RS_SERVER_URL"):
        return None

    rserver_url_bin = "/usr/lib/rstudio-server/bin/rserver-url"
    if not os.path.exists(rserver_url_bin):
        return None

    curl_bin = _which("curl")
    if not curl_bin:
        return None

    return RealWorkbenchInfo(rserver_url_bin=rserver_url_bin, curl_bin=curl_bin)


def get_rserver_external(port: int, *, rserver_url_bin: str) -> str:
    """
    Call rserver-url to get an external URL/prefix for the given port.
    """
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [rserver_url_bin, "-l", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return proc.stdout.strip()

