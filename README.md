# Encrypt in Snowflake, Decrypt in Your App

Encrypt sensitive columns using Snowflake `ENCRYPT_RAW` (AES-256-GCM). Decrypt them client-side with the same key.

## How it works

```
AWS KMS ──generates──► 32-byte key ──shared with──► Snowflake view (ENCRYPT_RAW)
                            │                              │
                            │                              ▼
                            └──────────────────────► Your app (AES-GCM decrypt)
```

1. Generate a 32-byte AES-256 key in AWS KMS
2. Snowflake view encrypts sensitive columns using that key
3. Your app fetches the same key from AWS and decrypts

## Quick start

### 1. Get a key

Run the helper script (creates a KMS key and stores it in Secrets Manager):

```bash
pip install -r requirements.txt
python setup_kms_key.py
```

Or generate one yourself — any 32-byte random key works:

```bash
python3 -c "import os; print(os.urandom(32).hex())"
```

### 2. Create the encrypted view in Snowflake

Edit `encrypt_view.sql` — replace `<32_BYTE_KEY_HEX>` with your 64-char hex key, then run it.

This creates:
- `CUSTOMER_BASE` — your table (plaintext, unchanged)
- `CUSTOMER_ENC_V` — a view that encrypts EMAIL, PHONE, ADDRESS, NATIONAL_ID on read

### 3. Decrypt in your app

```bash
export SNOWFLAKE_CONNECTION_NAME=default
python decrypt_client.py
```

The script fetches the key from Secrets Manager automatically. Or pass it directly:

```bash
export ENCRYPTION_KEY_HEX=<your_64_char_hex_key>
python decrypt_client.py
```

## Files

| File | What it does |
|---|---|
| `encrypt_view.sql` | Creates the base table, encrypted view, and RBAC grants |
| `setup_kms_key.py` | Generates a key via AWS KMS and stores it in Secrets Manager |
| `decrypt_client.py` | Queries the encrypted view and decrypts client-side |

## Production notes

- **Don't hardcode the key in SQL.** Use a [Snowflake external function + AWS Lambda](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws) to fetch it at runtime.
- **Key rotation:** Generate a new key, update the view and Secrets Manager. Decrypt old data with the old key first.
- **If you don't need external decryption**, consider [dynamic data masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro) instead — it's simpler.

## References

- [ENCRYPT_RAW docs](https://docs.snowflake.com/en/sql-reference/functions/encrypt_raw)
- [AWS KMS GenerateDataKey](https://docs.aws.amazon.com/kms/latest/APIReference/API_GenerateDataKey.html)
- [Python AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.aead.AESGCM)
