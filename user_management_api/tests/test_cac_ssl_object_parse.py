from __future__ import annotations

from types import SimpleNamespace

from app.routes import cac as cac_routes


def test_extract_identity_from_ssl_object_parses_der_cert() -> None:
    # Minimal self-signed DER cert bytes (generated once in test by cryptography).
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TEST CAC")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(1234)
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    der = cert.public_bytes(Encoding.DER)

    ssl_obj = SimpleNamespace(getpeercert=lambda binary_form=False: der if binary_form else {})
    ident = cac_routes._extract_identity_from_ssl_object(ssl_obj)
    assert ident
    assert ident["source"] == "asgi_ssl_object"
    assert ident["serial"] == format(1234, "x").upper()
    assert ident["common_name"] == "TEST CAC"

