from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import ipaddress
import requests


@dataclass(frozen=True)
class BackendClient:
    base_url: str
    admin_api_key: str = ""
    access_token: str = ""
    timeout_s: int = 10

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.admin_api_key:
            headers["X-Admin-Api-Key"] = self.admin_api_key
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def get(self, path: str, *, params: Optional[dict] = None) -> requests.Response:
        return requests.get(
            self._url(path),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_s,
        )

    def post_json(self, path: str, *, json: dict, params: Optional[dict] = None) -> requests.Response:
        return requests.post(
            self._url(path),
            params=params,
            json=json,
            headers=self._headers(),
            timeout=self.timeout_s,
        )

    def patch_json(self, path: str, *, json: dict) -> requests.Response:
        return requests.patch(
            self._url(path),
            json=json,
            headers=self._headers(),
            timeout=self.timeout_s,
        )

    def post_form(self, path: str, *, data: dict) -> requests.Response:
        return requests.post(
            self._url(path),
            data=data,
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout_s,
        )


def validate_backend_url(url: str, *, allow_local: bool = True) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.netloc:
        raise ValueError("BACKEND_URL must be a full http(s) URL")
    if p.username or p.password:
        raise ValueError("BACKEND_URL must not contain credentials")
    host = p.hostname or ""
    try:
        ip = ipaddress.ip_address(host)
        if allow_local and ip.is_loopback:
            return
        if ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError("BACKEND_URL must not target private/link-local IPs")
    except ValueError:
        return


def validate_streamlit_test_mode_backend(url: str) -> None:
    flag = os.getenv("STREAMLIT_TEST_MODE", "").lower()
    if flag not in ("1", "true", "yes"):
        return
    if url.rstrip("/") != "http://testserver":
        raise ValueError("STREAMLIT_TEST_MODE is only allowed with BACKEND_URL=http://testserver")


def safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {"data": data}

