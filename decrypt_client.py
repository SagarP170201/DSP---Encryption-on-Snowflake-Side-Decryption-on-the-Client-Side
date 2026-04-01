"""
Decrypt Snowflake ENCRYPT_RAW (AES-256-GCM) columns client-side.

Usage:
    export ENCRYPTION_KEY_HEX=<your_64_char_hex_key>
    export SNOWFLAKE_CONNECTION_NAME=default
    python decrypt_client.py
"""

import json
import os
import sys

import snowflake.connector
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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
    key_hex = os.environ.get("ENCRYPTION_KEY_HEX")
    if not key_hex:
        print("ERROR: Set ENCRYPTION_KEY_HEX env var (64-char hex key from KMS)", file=sys.stderr)
        sys.exit(1)

    conn = snowflake.connector.connect(
        connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "default"
    )

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM CUSTOMER_ENC_V")
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
