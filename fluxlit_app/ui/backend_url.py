"""Validate external backend base URLs (SSRF-hardening for configurable API roots)."""

from __future__ import annotations

import socket
import ipaddress
from urllib.parse import urlparse


def validate_backend_url(url: str, *, allow_local: bool = True) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.netloc:
        raise ValueError("BACKEND_URL must be a full http(s) URL")
    if p.username or p.password:
        raise ValueError("BACKEND_URL must not contain credentials")
    host = p.hostname or ""
    if allow_local and host.lower() in {"localhost", "testserver"}:
        return
    try:
        ip = ipaddress.ip_address(host)
        if allow_local and ip.is_loopback:
            return
        if ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError("BACKEND_URL must not target private/link-local IPs")
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, p.port or 443, type=socket.SOCK_STREAM)
        except OSError as e:
            raise ValueError("BACKEND_URL hostname could not be resolved") from e
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if allow_local and ip.is_loopback:
                continue
            if ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise ValueError(
                    "BACKEND_URL must not resolve to private/link-local IPs"
                )
        return
