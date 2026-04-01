"""
Application-side decryption for data encrypted with Snowflake ENCRYPT_RAW (AES-256-GCM).

The encryption key is fetched from AWS Secrets Manager (set up by setup_kms_key.py).
Falls back to the ENCRYPTION_KEY_HEX environment variable if AWS is unavailable.

Requirements:
    pip install -r requirements.txt

Usage:
    python decrypt_client.py [--secret-name snowflake/encrypt-raw/data-key] [--region us-east-1]

Environment variables (optional overrides):
    ENCRYPTION_KEY_HEX          - 64-char hex key (skips Secrets Manager)
    SNOWFLAKE_CONNECTION_NAME   - Snowflake connection from ~/.snowflake/connections.toml
    AWS_DEFAULT_REGION          - AWS region for Secrets Manager
"""

import argparse
import json
import os
import sys

import snowflake.connector
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_SECRET_NAME = "snowflake/encrypt-raw/data-key"


def get_key_from_secrets_manager(secret_name: str, region: str = None) -> str:
    try:
        import boto3
        session = boto3.Session(region_name=region)
        client = session.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response["SecretString"])
        return secret["key_hex"]
    except Exception as e:
        print(f"Warning: Could not fetch key from Secrets Manager ({e})")
        return None


def get_encryption_key(secret_name: str, region: str = None) -> str:
    env_key = os.environ.get("ENCRYPTION_KEY_HEX")
    if env_key:
        print("Using encryption key from ENCRYPTION_KEY_HEX environment variable")
        return env_key

    print(f"Fetching encryption key from AWS Secrets Manager ({secret_name})...")
    key = get_key_from_secrets_manager(secret_name, region)
    if key:
        return key

    print("ERROR: No encryption key available.", file=sys.stderr)
    print("  Option 1: Run setup_kms_key.py first to generate and store a key", file=sys.stderr)
    print("  Option 2: Set ENCRYPTION_KEY_HEX environment variable", file=sys.stderr)
    sys.exit(1)


def decrypt_column(encrypted_variant: dict, key_hex: str) -> str:
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(encrypted_variant["iv"])
    ciphertext = bytes.fromhex(encrypted_variant["ciphertext"])
    tag = bytes.fromhex(encrypted_variant["tag"])

    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(
        nonce=iv,
        data=ciphertext + tag,  # AES-GCM expects ciphertext || tag
        associated_data=None,   # must match NULL AAD from ENCRYPT_RAW
    )
    return plaintext_bytes.decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Decrypt Snowflake ENCRYPT_RAW columns client-side")
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME, help="AWS Secrets Manager secret name")
    parser.add_argument("--region", default=None, help="AWS region")
    parser.add_argument("--query", default="SELECT * FROM CUSTOMER_ENC_V", help="SQL query to run")
    args = parser.parse_args()

    key_hex = get_encryption_key(args.secret_name, args.region)

    conn = snowflake.connector.connect(
        connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "default"
    )

    try:
        cur = conn.cursor()
        cur.execute(args.query)
        columns = [desc[0] for desc in cur.description]

        enc_columns = [c for c in columns if c.endswith("_ENC")]

        for row in cur:
            row_dict = dict(zip(columns, row))

            non_enc = {k: v for k, v in row_dict.items() if not k.endswith("_ENC")}
            print(f"\n--- {non_enc} ---")

            for col in enc_columns:
                variant = row_dict[col]
                if variant is None:
                    print(f"  {col} -> NULL")
                    continue
                if isinstance(variant, str):
                    variant = json.loads(variant)
                plaintext = decrypt_column(variant, key_hex)
                print(f"  {col} -> {plaintext}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
