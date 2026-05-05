## CAC / mTLS nginx layer (local)

This folder provides a local nginx TLS terminator that:

- requires a client certificate (CAC) via **mTLS**
- (optionally) checks revocation using a CRL bundle
- forwards **proxy-generated** identity headers to the backend so they cannot be spoofed by callers

### Files you must provide (not committed)

Create these files (or mount them) before starting:

- `certs/server.crt`: server certificate (PEM)
- `certs/server.key`: server private key (PEM)
- `certs/dod_ca_bundle.pem`: DoD trust chain bundle used to verify client certs (PEM)
- `certs/dod_crl_bundle.pem` (optional): CRL bundle (PEM), see `build_crl_bundle.sh`

### Build a CRL bundle from `ALLCRLZIP` (optional)

If you downloaded the DoD CRLs directory at `~/Downloads/ALLCRLZIP`:

```bash
./build_crl_bundle.sh "/Users/odosmatthews/Downloads/ALLCRLZIP" certs/dod_crl_bundle.pem
```

Note: `ALLCRLZIP` contains CRLs, not CA certs. You still need a CA trust bundle
(`dod_ca_bundle.pem`) from an approved source.

### Start

From repo root:

```bash
docker compose -f infra/cac-nginx/docker-compose.yml up --build
```

Then browse:

- `https://127.0.0.1:8443/auth/cac/whoami`

If your browser has a CAC available and the CA bundle matches, you should see the
client identity details.

