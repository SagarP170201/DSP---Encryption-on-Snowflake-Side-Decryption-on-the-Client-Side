# Encrypt in Snowflake, Decrypt in Your App

Encrypt sensitive columns using Snowflake `ENCRYPT_RAW` (AES-256-GCM). Decrypt them client-side using your existing AWS KMS key.

## How it works

```
Your KMS key (32-byte hex) ──► Snowflake view (ENCRYPT_RAW) ──► Your app (AES-GCM decrypt)
```

1. Your existing KMS key is used in a Snowflake view to encrypt sensitive columns
2. Your app uses the same key to decrypt client-side

## Prerequisites

- Your **AWS KMS key** (32-byte / 64-char hex string)
- **Python 3.8+**
- **Snowflake account** with a configured connection

## Quick start

### Step 1: Create the encrypted view in Snowflake

Edit `encrypt_view.sql` — replace every `<32_BYTE_KEY_HEX>` with your 64-char hex key from KMS.

Run it in a Snowflake worksheet. Test it:

```sql
INSERT INTO CUSTOMER_BASE VALUES (1, 'Alice', 'alice@example.com', '555-0101', '123 Main St', 'NID-1001');
ALTER SESSION SET BINARY_OUTPUT_FORMAT = 'HEX';
SELECT * FROM CUSTOMER_ENC_V;
```

Each encrypted column returns: `{ "iv": "...", "ciphertext": "...", "tag": "..." }`

### Step 2: Decrypt in your app

```bash
pip install -r requirements.txt
export ENCRYPTION_KEY_HEX=<your_64_char_hex_key>
export SNOWFLAKE_CONNECTION_NAME=default
python decrypt_client.py
```

## Files

| File | What it does |
|---|---|
| `encrypt_view.sql` | Creates the base table, encrypted view, and RBAC grants |
| `decrypt_client.py` | Queries the encrypted view and decrypts client-side |
| `requirements.txt` | Python dependencies |

## Production notes

- **Key in view DDL:** The hex key is visible via `GET_DDL`. For production, use a [Snowflake external function + Lambda](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws) so the key never appears in SQL.
- **If you don't need external decryption**, [dynamic data masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro) is simpler.

## References

- [ENCRYPT_RAW docs](https://docs.snowflake.com/en/sql-reference/functions/encrypt_raw)
- [Python AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.aead.AESGCM)
