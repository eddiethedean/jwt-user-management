#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="${ROOT_DIR}/certs"
TMP_DIR="${CERT_DIR}/tmp"

mkdir -p "${TMP_DIR}"

ZIP_URL="${ALLCRLZIP_URL:-https://crl.gds.disa.mil/getcrlzip?ALL+CRL+ZIP}"
ZIP_PATH="${TMP_DIR}/ALLCRLZIP.zip"
UNZIP_DIR="${TMP_DIR}/ALLCRLZIP"
OUT_FILE="${CERT_DIR}/dod_crl_bundle.pem"

echo "==> Downloading ALLCRLZIP"
echo "    ${ZIP_URL}"
curl -L -A "Mozilla/5.0" -o "${ZIP_PATH}" "${ZIP_URL}"

echo "==> Unzipping"
rm -rf "${UNZIP_DIR}"
mkdir -p "${UNZIP_DIR}"
unzip -o "${ZIP_PATH}" -d "${UNZIP_DIR}" >/dev/null

echo "==> Building CRL bundle PEM"
rm -f "${OUT_FILE}"
"${ROOT_DIR}/build_crl_bundle.sh" "${UNZIP_DIR}" "${OUT_FILE}"

echo "Done: ${OUT_FILE}"

