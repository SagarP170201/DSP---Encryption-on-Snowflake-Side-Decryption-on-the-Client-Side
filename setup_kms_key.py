"""
AWS KMS key generation and Secrets Manager storage for Snowflake ENCRYPT_RAW.

This script:
  1. Creates (or reuses) a KMS Customer Master Key (CMK)
  2. Generates a 32-byte AES-256 data key using that CMK
  3. Stores the plaintext hex key in AWS Secrets Manager

Prerequisites:
  - AWS CLI configured (aws configure)
  - IAM permissions: kms:CreateKey, kms:GenerateDataKey, kms:DescribeKey,
    kms:ListKeys, secretsmanager:CreateSecret, secretsmanager:PutSecretValue

Usage:
  python setup_kms_key.py [--cmk-description "My key"] [--secret-name snowflake/encrypt-raw/data-key]
"""

import argparse
import json
import sys

import boto3
from botocore.exceptions import ClientError

DEFAULT_CMK_DESCRIPTION = "Snowflake ENCRYPT_RAW data encryption key"
DEFAULT_SECRET_NAME = "snowflake/encrypt-raw/data-key"


def find_or_create_cmk(kms_client, description: str) -> str:
    paginator = kms_client.get_paginator("list_keys")
    for page in paginator.paginate():
        for key_meta in page["Keys"]:
            try:
                info = kms_client.describe_key(KeyId=key_meta["KeyId"])
                if (
                    info["KeyMetadata"]["Description"] == description
                    and info["KeyMetadata"]["KeyState"] == "Enabled"
                ):
                    key_id = info["KeyMetadata"]["KeyId"]
                    print(f"Found existing CMK: {key_id}")
                    return key_id
            except ClientError:
                continue

    response = kms_client.create_key(
        Description=description,
        KeyUsage="ENCRYPT_DECRYPT",
        KeySpec="SYMMETRIC_DEFAULT",
    )
    key_id = response["KeyMetadata"]["KeyId"]
    print(f"Created new CMK: {key_id}")
    return key_id


def generate_data_key(kms_client, cmk_id: str) -> tuple:
    response = kms_client.generate_data_key(KeyId=cmk_id, KeySpec="AES_256")
    plaintext_hex = response["Plaintext"].hex()
    ciphertext_blob_hex = response["CiphertextBlob"].hex()
    print(f"Generated 32-byte AES-256 data key (64 hex chars)")
    print(f"  Plaintext key (hex): {plaintext_hex[:8]}...{plaintext_hex[-8:]}")
    return plaintext_hex, ciphertext_blob_hex


def store_in_secrets_manager(sm_client, secret_name: str, key_hex: str, wrapped_key_hex: str):
    secret_value = json.dumps({
        "key_hex": key_hex,
        "wrapped_key_hex": wrapped_key_hex,
    })

    try:
        sm_client.create_secret(Name=secret_name, SecretString=secret_value)
        print(f"Stored key in Secrets Manager: {secret_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            sm_client.put_secret_value(SecretId=secret_name, SecretString=secret_value)
            print(f"Updated existing secret: {secret_name}")
        else:
            raise


def main():
    parser = argparse.ArgumentParser(description="Generate AES-256 key via AWS KMS for Snowflake ENCRYPT_RAW")
    parser.add_argument("--cmk-description", default=DEFAULT_CMK_DESCRIPTION)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--region", default=None, help="AWS region (uses default if not set)")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    kms_client = session.client("kms")
    sm_client = session.client("secretsmanager")

    cmk_id = find_or_create_cmk(kms_client, args.cmk_description)
    key_hex, wrapped_key_hex = generate_data_key(kms_client, cmk_id)
    store_in_secrets_manager(sm_client, args.secret_name, key_hex, wrapped_key_hex)

    print("\n--- Next steps ---")
    print(f"1. Copy the key_hex from Secrets Manager ('{args.secret_name}')")
    print(f"2. Replace <32_BYTE_KEY_HEX> in encrypt_view.sql with that 64-char hex value")
    print(f"3. Run encrypt_view.sql in Snowflake")
    print(f"4. Run: python decrypt_client.py")


if __name__ == "__main__":
    main()
