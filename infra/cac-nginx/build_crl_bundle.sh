#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="${1:-}"
OUT_FILE="${2:-}"

if [[ -z "${SRC_DIR}" || -z "${OUT_FILE}" ]]; then
  echo "Usage: $0 <ALLCRLZIP_dir> <output_pem_file>" >&2
  exit 2
fi

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "ERROR: source dir not found: ${SRC_DIR}" >&2
  exit 2
fi

tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT

count=0
for crl in "${SRC_DIR}"/*.crl; do
  # zsh can pass literal glob when empty; guard.
  if [[ ! -f "${crl}" ]]; then
    continue
  fi
  # Most DoD .crl files are DER. Convert to PEM.
  openssl crl -inform DER -in "${crl}" -out "${tmp}" 2>/dev/null || {
    echo "WARN: failed to parse as DER, trying PEM: ${crl}" >&2
    openssl crl -inform PEM -in "${crl}" -out "${tmp}"
  }
  cat "${tmp}" >> "${OUT_FILE}"
  echo "" >> "${OUT_FILE}"
  count=$((count + 1))
done

if [[ "${count}" -eq 0 ]]; then
  echo "ERROR: no .crl files found in ${SRC_DIR}" >&2
  exit 2
fi

echo "Wrote ${count} CRLs to ${OUT_FILE}"

