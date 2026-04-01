"""
Generate a 32-byte AES-256 data key from your existing AWS KMS CMK.

Outputs:
  - Plaintext key (hex) — use in encrypt_view.sql and for decryption
  - CiphertextBlob (base64) — safe to store, pass to KMS decrypt at runtime

Prerequisites:
  - AWS credentials configured (aws configure)
  - IAM permissions: kms:GenerateDataKey on your CMK

Usage:
  python setup_kms_key.py --key-id <YOUR_CMK_KEY_ID_OR_ALIAS>
  python setup_kms_key.py --key-id alias/my-key
"""

import argparse
import base64

import boto3


def main():
    parser = argparse.ArgumentParser(description="Generate AES-256 data key from existing KMS CMK")
    parser.add_argument("--key-id", required=True, help="KMS CMK key ID, ARN, or alias (e.g. alias/my-key)")
    parser.add_argument("--region", default=None, help="AWS region")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    kms_client = session.client("kms")

    response = kms_client.generate_data_key(KeyId=args.key_id, KeySpec="AES_256")

    plaintext_hex = response["Plaintext"].hex()
    ciphertext_blob_b64 = base64.b64encode(response["CiphertextBlob"]).decode("utf-8")

    print(f"Plaintext key (hex) — use in encrypt_view.sql:")
    print(f"  {plaintext_hex}")
    print()
    print(f"CiphertextBlob (base64) — set as KMS_ENCRYPTED_KEY_BLOB env var:")
    print(f"  {ciphertext_blob_b64}")
    print()
    print("--- Next steps ---")
    print(f"1. Replace <32_BYTE_KEY_HEX> in encrypt_view.sql with: {plaintext_hex}")
    print(f"2. Run encrypt_view.sql in Snowflake")
    print(f"3. export KMS_ENCRYPTED_KEY_BLOB={ciphertext_blob_b64}")
    print(f"4. python decrypt_client.py")


if __name__ == "__main__":
    main()
