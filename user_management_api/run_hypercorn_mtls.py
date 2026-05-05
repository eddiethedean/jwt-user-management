from __future__ import annotations

import os
import ssl
from pathlib import Path

from hypercorn.asyncio import serve
from hypercorn.config import Config

from app.asgi import app


def _default_cert_path(rel_from_repo_root: str) -> str:
    """
    This script is typically run from `user_management_api/`, but the certs live
    under `infra/cac-nginx/certs/` at the repo root.
    """
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / rel_from_repo_root)


def main() -> None:
    cfg = Config()
    cfg.bind = [os.getenv("BIND", "127.0.0.1:8443")]

    cfg.certfile = os.getenv(
        "TLS_CERTFILE", _default_cert_path("infra/cac-nginx/certs/server.crt")
    )
    cfg.keyfile = os.getenv(
        "TLS_KEYFILE", _default_cert_path("infra/cac-nginx/certs/server.key")
    )
    cfg.ca_certs = os.getenv(
        "TLS_CA_CERTS", _default_cert_path("infra/cac-nginx/certs/dod_ca_bundle.pem")
    )

    # Optional: CRL checks aren't directly exposed as a first-class hypercorn config,
    # so revocation should be handled at a proxy in production. For local experiments,
    # we focus on prompting for CAC and surfacing the cert.

    # Request a client certificate; require it only for /auth/cac/* at the app layer.
    # If you want to require CAC for *all* endpoints, set this to CERT_REQUIRED.
    cfg.verify_mode = ssl.CERT_OPTIONAL

    # Hypercorn is async; run it.
    import asyncio

    asyncio.run(serve(app, cfg))


if __name__ == "__main__":
    main()

