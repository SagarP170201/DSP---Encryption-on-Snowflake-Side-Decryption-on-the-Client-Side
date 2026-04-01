# Encrypt in Snowflake, Decrypt in Your App

Encrypt sensitive columns using Snowflake `ENCRYPT_RAW` (AES-256-GCM). Decrypt them client-side using your existing AWS KMS key.

## How it works

```
Your KMS key (32-byte hex) ──► Snowflake view (ENCRYPT_RAW) ──► Your app (AES-GCM decrypt)
```

1. Your existing KMS key is used in a Snowflake view to encrypt 4 sensitive columns on read
2. Base table stays plaintext — only the view output is encrypted
3. Your app decrypts client-side using the same key

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
NULL columns return NULL (no error).

### Step 2: Decrypt in your app

```bash
pip install -r requirements.txt
export ENCRYPTION_KEY_HEX=<your_64_char_hex_key>
export SNOWFLAKE_CONNECTION_NAME=default
python decrypt_client.py
```

## Security (RBAC)

The encryption key lives in the view definition. Tighten access to prevent exposure:

```sql
-- Only admin roles should be able to see the view DDL
REVOKE ALL ON VIEW CUSTOMER_ENC_V FROM ROLE SYSADMIN;
GRANT SELECT ON VIEW CUSTOMER_ENC_V TO ROLE APP_ROLE;

-- Verify who can run GET_DDL on the view — restrict to crypto-admin only
SHOW GRANTS ON VIEW CUSTOMER_ENC_V;
```

Anyone who can run `GET_DDL('VIEW', 'CUSTOMER_ENC_V')` can see the key. Treat that permission as crypto-admin level.

## Files

| File | What it does |
|---|---|
| `encrypt_view.sql` | Creates the base table, encrypted view (with NULL handling), and RBAC grants |
| `decrypt_client.py` | Queries the encrypted view and decrypts client-side |
| `requirements.txt` | Python dependencies |

## Production upgrade path

If the key must never appear in Snowflake SQL, the next step is:
**Snowflake external function → AWS API Gateway → Lambda → KMS**

Lambda encrypts the data using the key fetched from KMS at runtime. Key never enters Snowflake. See [Snowflake external functions on AWS](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws).

## References

- [ENCRYPT_RAW docs](https://docs.snowflake.com/en/sql-reference/functions/encrypt_raw)
- [Python AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.aead.AESGCM)
