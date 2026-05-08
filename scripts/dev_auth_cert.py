#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys

DEFAULT_DIR = Path("dev-certs")


def run_openssl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["openssl", *args],
        capture_output=True,
        text=True,
    )


def ensure_openssl_available() -> None:
    try:
        proc = run_openssl(["version"])
    except FileNotFoundError:
        print("ERROR: OpenSSL is required but not installed or not on PATH.")
        sys.exit(2)
    if proc.returncode != 0:
        print("ERROR: OpenSSL invocation failed:")
        print(proc.stderr.strip())
        sys.exit(2)


def generate_dev_ca(certs_dir: Path, days: int) -> tuple[Path, Path]:
    ca_key = certs_dir / "dev-ca.key.pem"
    ca_cert = certs_dir / "dev-ca.crt.pem"

    if not ca_key.exists():
        print(f"Generating CA private key: {ca_key}")
        proc = run_openssl([
            "genpkey",
            "-algorithm",
            "RSA",
            "-out",
            str(ca_key),
            "-pkeyopt",
            "rsa_keygen_bits:4096",
        ])
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip())

    if not ca_cert.exists():
        print(f"Generating CA certificate: {ca_cert}")
        proc = run_openssl([
            "req",
            "-x509",
            "-new",
            "-nodes",
            "-key",
            str(ca_key),
            "-sha256",
            "-days",
            str(days),
            "-out",
            str(ca_cert),
            "-subj",
            "/CN=K1 Dev CA",
        ])
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip())

    return ca_key, ca_cert


def generate_dev_client_cert(certs_dir: Path, days: int) -> tuple[Path, Path]:
    client_key = certs_dir / "dev-client.key.pem"
    client_csr = certs_dir / "dev-client.csr.pem"
    client_cert = certs_dir / "dev-client.crt.pem"
    ca_key = certs_dir / "dev-ca.key.pem"
    ca_cert = certs_dir / "dev-ca.crt.pem"

    if not client_key.exists():
        print(f"Generating client private key: {client_key}")
        proc = run_openssl([
            "genpkey",
            "-algorithm",
            "RSA",
            "-out",
            str(client_key),
            "-pkeyopt",
            "rsa_keygen_bits:2048",
        ])
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip())

    print(f"Generating client CSR: {client_csr}")
    proc = run_openssl([
        "req",
        "-new",
        "-key",
        str(client_key),
        "-out",
        str(client_csr),
        "-subj",
        "/CN=K1 Dev Client",
    ])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())

    print(f"Signing client certificate: {client_cert}")
    proc = run_openssl([
        "x509",
        "-req",
        "-in",
        str(client_csr),
        "-CA",
        str(ca_cert),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-out",
        str(client_cert),
        "-days",
        str(days),
        "-sha256",
    ])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())

    return client_key, client_cert


def print_instructions(certs_dir: Path, ca_cert: Path, client_cert: Path) -> None:
    print("\nDev certificate generation complete.")
    print(f"CA certificate: {ca_cert}")
    print(f"Client certificate: {client_cert}")
    print("\nTo use this certificate for dev-only auth, set the following in your local environment:")
    print("  K1_DEV_CERT_AUTH_ENABLED=true")
    print(f"  K1_DEV_AUTH_CA_PATH={ca_cert}")
    print("\nThen POST the signed client certificate PEM to /auth/token/dev-cert.")
    print("The certificate is valid only for the configured lifetime and is not a hardcoded static token.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a local dev CA and client certificate for K1 dev authentication.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DIR,
        help="Directory to write the dev CA and client certificate files.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to keep generated certs valid.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing certificate material if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_openssl_available()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.force:
        for path in args.output_dir.glob("dev-*.pem"):
            path.unlink(missing_ok=True)

    ca_key, ca_cert = generate_dev_ca(args.output_dir, args.days)
    client_key, client_cert = generate_dev_client_cert(args.output_dir, args.days)
    print_instructions(args.output_dir, ca_cert, client_cert)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
