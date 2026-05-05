#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "${CERT_DIR}/tmp"

echo "==> Downloading DoD CA bundle (PKCS#7)"
ZIP_URL="${DOD_PKI_ZIP_URL:-https://crl.gds.disa.mil/pke/config/certificates_pkcs7_dod.zip}"
ZIP_PATH="${CERT_DIR}/tmp/certificates_pkcs7_dod.zip"

curl -L -A "Mozilla/5.0" -o "${ZIP_PATH}" "${ZIP_URL}"

echo "==> Extracting PKCS#7 and converting to PEM bundle"
unzip -o "${ZIP_PATH}" "*/Certificates_PKCS7_v5_14_DoD.pem.p7b" -d "${CERT_DIR}/tmp/extracted" >/dev/null
P7B_PATH="${CERT_DIR}/tmp/extracted/Certificates_PKCS7_v5_14_DoD/Certificates_PKCS7_v5_14_DoD.pem.p7b"
openssl pkcs7 -print_certs -in "${P7B_PATH}" -out "${CERT_DIR}/dod_ca_bundle.pem"

echo "==> Generating local self-signed server cert (for development)"
if [[ ! -f "${CERT_DIR}/server.crt" || ! -f "${CERT_DIR}/server.key" ]]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -days 30 -nodes \
    -subj "/CN=localhost" \
    -keyout "${CERT_DIR}/server.key" \
    -out "${CERT_DIR}/server.crt"
else
  echo "    server.crt/server.key already exist; skipping"
fi

if [[ "${1:-}" != "" ]]; then
  ALLCRLZIP_DIR="$1"
  echo "==> Building CRL bundle from ${ALLCRLZIP_DIR}"
  "$(cd "$(dirname "$0")" && pwd)/build_crl_bundle.sh" "${ALLCRLZIP_DIR}" "${CERT_DIR}/dod_crl_bundle.pem"
else
  echo "==> Skipping CRL bundle (pass ALLCRLZIP dir to build)"
fi

echo "Done."

