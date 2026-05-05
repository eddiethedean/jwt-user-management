from __future__ import annotations

import ssl
from typing import Any, Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth/cac", tags=["cac"])


def _first_header(request: Request, name: str) -> str:
    v = request.headers.get(name, "")
    return (v or "").strip()


def _extract_forwarded_client_cert_pem(request: Request) -> str:
    """
    Common reverse-proxy patterns:
    - Nginx: `proxy_set_header X-SSL-Client-Cert $ssl_client_escaped_cert;`
    - Some proxies use `X-Forwarded-Client-Cert` (may be URL-escaped, or include metadata).
    """
    pem = _first_header(request, "X-SSL-Client-Cert")
    if pem:
        return pem
    xfcc = _first_header(request, "X-Forwarded-Client-Cert")
    if xfcc:
        return xfcc
    return ""


def _extract_identity_from_headers(request: Request) -> Optional[dict[str, Any]]:
    verify = _first_header(request, "X-SSL-Client-Verify") or _first_header(
        request, "X-Client-Verify"
    )
    if verify and verify.upper() not in {"SUCCESS", "OK", "TRUE", "1"}:
        raise HTTPException(status_code=401, detail="Client certificate not verified")

    dn = _first_header(request, "X-SSL-Client-S-DN") or _first_header(request, "X-Client-DN")
    issuer = _first_header(request, "X-SSL-Client-I-DN") or _first_header(
        request, "X-Client-Issuer"
    )
    serial = _first_header(request, "X-SSL-Client-Serial") or _first_header(
        request, "X-Client-Serial"
    )
    pem = _extract_forwarded_client_cert_pem(request)

    if any([verify, dn, issuer, serial, pem]):
        return {
            "source": "headers",
            "verified": True if verify else None,
            "subject_dn": dn or None,
            "issuer_dn": issuer or None,
            "serial": serial or None,
            "client_cert": pem or None,
        }
    return None


def _extract_identity_from_asgi_scope(request: Request) -> Optional[dict[str, Any]]:
    """
    If Hypercorn terminates TLS and exposes TLS info to the app, it will be present
    on the ASGI scope. There isn't one universally consistent field across all
    ASGI servers, so we probe a few common spots.
    """
    scope = request.scope
    extensions = scope.get("extensions") or {}

    # ASGI TLS extension (if supported): https://asgi.readthedocs.io/en/latest/specs/tls.html
    tls = extensions.get("tls") if isinstance(extensions, dict) else None
    if isinstance(tls, dict):
        return {
            "source": "asgi_tls_extension",
            "tls": tls,
        }

    ssl_obj = scope.get("ssl_object") or scope.get("ssl")
    if ssl_obj is not None:
        ident = _extract_identity_from_ssl_object(ssl_obj)
        if ident is not None:
            return ident
        # Fallback: don't assume methods/shape; just return presence + repr.
        return {"source": "asgi_ssl_object", "ssl_object_repr": repr(ssl_obj)}

    return None


def _name_to_rfc4514(name: x509.Name) -> str:
    # x509.Name.rfc4514_string() exists, but we keep a stable-ish representation.
    try:
        return name.rfc4514_string()
    except Exception:
        parts = []
        for rdn in name.rdns:
            for attr in rdn:
                parts.append(f"{attr.oid.dotted_string}={attr.value}")
        return ",".join(parts)


def _extract_identity_from_ssl_object(ssl_obj: Any) -> Optional[dict[str, Any]]:
    """
    Extract client certificate details from an SSLObject/SSLSocket if present.
    This is the preferred mode for Hypercorn-only deployments.
    """
    # Hypercorn may provide an ssl.SSLObject / ssl.SSLSocket
    if not hasattr(ssl_obj, "getpeercert"):
        return None

    try:
        der: Optional[bytes] = ssl_obj.getpeercert(binary_form=True)
    except Exception:
        der = None

    if not der:
        return None

    try:
        cert = x509.load_der_x509_certificate(der)
    except Exception as e:
        return {
            "source": "asgi_ssl_object",
            "error": f"failed to parse client certificate: {type(e).__name__}",
        }

    subject_dn = _name_to_rfc4514(cert.subject)
    issuer_dn = _name_to_rfc4514(cert.issuer)
    serial_hex = format(cert.serial_number, "x").upper()

    # Common CAC attributes: CN and sometimes UPN in SubjectAltName (not parsed here).
    cn = None
    try:
        cn_attr = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attr:
            cn = cn_attr[0].value
    except Exception:
        cn = None

    pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8", errors="ignore")

    return {
        "source": "asgi_ssl_object",
        "verified": True,  # if we have a peer cert, the TLS layer accepted it
        "subject_dn": subject_dn,
        "issuer_dn": issuer_dn,
        "serial": serial_hex,
        "common_name": cn,
        "client_cert": pem,
    }


@router.get("/whoami")
async def cac_whoami(request: Request) -> JSONResponse:
    """
    Returns verified client credential material (CAC) if present.

    IMPORTANT: This endpoint only becomes useful once you enable mTLS at the TLS
    terminator (Hypercorn or a reverse proxy) and forward/attach the identity.
    """
    ident = _extract_identity_from_headers(request)
    if ident is None:
        ident = _extract_identity_from_asgi_scope(request)

    if ident is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "No client certificate credentials found. "
                "Enable mTLS at the TLS terminator and forward identity."
            ),
        )

    return JSONResponse(content={"ok": True, "cac": ident})

