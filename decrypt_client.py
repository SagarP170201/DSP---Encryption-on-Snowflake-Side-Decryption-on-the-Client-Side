"""
Application-side decryption for data encrypted with Snowflake ENCRYPT_RAW (AES-256-GCM).

Requirements:
    pip install cryptography snowflake-connector-python

Usage:
    1. Replace <32_BYTE_KEY_HEX> with your 64-char hex key from AWS KMS / Secrets Manager.
    2. Replace connection parameters or use SNOWFLAKE_CONNECTION_NAME env var.
    3. Run: python decrypt_client.py
"""

import os
import json
import snowflake.connector
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def decrypt_column(encrypted_variant: dict, key_hex: str) -> str:
    """Decrypt a single ENCRYPT_RAW output (VARIANT with iv, ciphertext, tag)."""
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
    key_hex = os.environ.get("ENCRYPTION_KEY_HEX", "<32_BYTE_KEY_HEX>")

    conn = snowflake.connector.connect(
        connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or "default"
    )

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM CUSTOMER_ENC_V")
        columns = [desc[0] for desc in cur.description]

        enc_columns = ["EMAIL_ENC", "PHONE_ENC", "ADDRESS_ENC", "NATIONAL_ID_ENC"]

        for row in cur:
            row_dict = dict(zip(columns, row))
            print(f"\n--- Row ID: {row_dict['ID']}, Name: {row_dict['NAME']} ---")

            for col in enc_columns:
                variant = row_dict[col]
                if isinstance(variant, str):
                    variant = json.loads(variant)
                plaintext = decrypt_column(variant, key_hex)
                print(f"  {col} -> {plaintext}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
