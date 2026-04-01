"""
Application-side decryption for data encrypted with Snowflake ENCRYPT_RAW (AES-256-GCM).

Key retrieval (in priority order):
  1. ENCRYPTION_KEY_HEX env var (direct plaintext hex key — for testing)
  2. KMS_ENCRYPTED_KEY_BLOB env var (base64 CiphertextBlob — calls KMS decrypt)

Requirements:
    pip install -r requirements.txt

Usage:
    export KMS_ENCRYPTED_KEY_BLOB=<base64_CiphertextBlob>
    export SNOWFLAKE_CONNECTION_NAME=default
    python decrypt_client.py
"""

import argparse
import base64
import json
import os
import sys

import snowflake.connector
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_key_from_kms(encrypted_key_blob_b64: str, region: str = None) -> str:
    import boto3
    session = boto3.Session(region_name=region)
    client = session.client("kms")
    response = client.decrypt(CiphertextBlob=base64.b64decode(encrypted_key_blob_b64))
    return response["Plaintext"].hex()


def get_encryption_key(region: str = None) -> str:
    env_key = os.environ.get("ENCRYPTION_KEY_HEX")
    if env_key:
        print("Using encryption key from ENCRYPTION_KEY_HEX env var")
        return env_key

    blob = os.environ.get("KMS_ENCRYPTED_KEY_BLOB")
    if blob:
        print("Decrypting key via AWS KMS...")
        return get_key_from_kms(blob, region)

    print("ERROR: No encryption key available.", file=sys.stderr)
    print("  Set ENCRYPTION_KEY_HEX (plaintext hex) or KMS_ENCRYPTED_KEY_BLOB (base64 blob)", file=sys.stderr)
    sys.exit(1)


def decrypt_column(encrypted_variant: dict, key_hex: str) -> str:
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(encrypted_variant["iv"])
    ciphertext = bytes.fromhex(encrypted_variant["ciphertext"])
    tag = bytes.fromhex(encrypted_variant["tag"])

    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(
        nonce=iv,
        data=ciphertext + tag,
        associated_data=None,
    )
    return plaintext_bytes.decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Decrypt Snowflake ENCRYPT_RAW columns client-side")
    parser.add_argument("--region", default=None, help="AWS region for KMS")
    parser.add_argument("--query", default="SELECT * FROM CUSTOMER_ENC_V", help="SQL query to run")
    args = parser.parse_args()

    key_hex = get_encryption_key(args.region)

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
