from __future__ import annotations

import os
import ssl

from hypercorn.asyncio import serve
from hypercorn.config import Config

from app.asgi import app


def main() -> None:
    cfg = Config()
    cfg.bind = [os.getenv("BIND", "127.0.0.1:8443")]

    cfg.certfile = os.getenv("TLS_CERTFILE", "infra/cac-nginx/certs/server.crt")
    cfg.keyfile = os.getenv("TLS_KEYFILE", "infra/cac-nginx/certs/server.key")
    cfg.ca_certs = os.getenv("TLS_CA_CERTS", "infra/cac-nginx/certs/dod_ca_bundle.pem")

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

