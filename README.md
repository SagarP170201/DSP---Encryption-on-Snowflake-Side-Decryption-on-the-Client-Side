# Encrypt in Snowflake, Decrypt in Your App

Encrypt sensitive columns using Snowflake `ENCRYPT_RAW` (AES-256-GCM). Decrypt them client-side using a key from your existing AWS KMS.

## How it works

```
Your existing AWS KMS CMK
         │
         ├── generate_data_key ──► plaintext key (32 bytes) + encrypted key blob
         │                              │                          │
         │                              ▼                          ▼
         │                     Snowflake ENCRYPT_RAW        Store blob with
         │                     (in view definition)         your app / config
         │
         └── kms.decrypt(blob) ──► plaintext key ──► App decrypts with AES-GCM
```

1. Use your existing KMS CMK to generate a 32-byte data key (`generate_data_key`)
2. Use that key in Snowflake `ENCRYPT_RAW` to encrypt sensitive columns in a view
3. Your app calls KMS `decrypt` on the stored key blob to get the plaintext key, then decrypts

## Prerequisites

- Existing **AWS KMS CMK** (you already have this)
- **Python 3.8+** with `pip install -r requirements.txt`
- **Snowflake account** and a configured connection
- IAM permissions: `kms:GenerateDataKey`, `kms:Decrypt` on your CMK

## Quick start

### Step 1: Generate a data key from your existing CMK

In **AWS CloudShell** (or any terminal with AWS credentials):

```bash
aws kms generate-data-key --key-id <YOUR_CMK_KEY_ID_OR_ALIAS> --key-spec AES_256
```

This returns:
- `Plaintext` — base64-encoded 32-byte key (used in Snowflake + app decryption)
- `CiphertextBlob` — encrypted version of the key (safe to store anywhere)

Convert the plaintext to hex:

```bash
echo "<PASTE_PLAINTEXT_BASE64>" | base64 --decode | xxd -p -c 64
```

Save both values:
- The **64-char hex string** → goes into `encrypt_view.sql` and is used by the app at runtime
- The **CiphertextBlob** (base64) → store it in your app config / env var / database — your app will pass this to KMS `decrypt` to recover the key at runtime

### Step 2: Create the encrypted view in Snowflake

Edit `encrypt_view.sql` — replace every `<32_BYTE_KEY_HEX>` with the 64-char hex key from Step 1.

Run it in a Snowflake worksheet. Test it:

```sql
INSERT INTO CUSTOMER_BASE VALUES (1, 'Alice', 'alice@example.com', '555-0101', '123 Main St', 'NID-1001');
ALTER SESSION SET BINARY_OUTPUT_FORMAT = 'HEX';
SELECT * FROM CUSTOMER_ENC_V;
```

Each encrypted column returns: `{ "iv": "...", "ciphertext": "...", "tag": "..." }`

### Step 3: Decrypt in your app

```bash
pip install -r requirements.txt
export KMS_ENCRYPTED_KEY_BLOB=<base64_CiphertextBlob_from_step_1>
export SNOWFLAKE_CONNECTION_NAME=default
python decrypt_client.py
```

The app calls KMS `decrypt` on the blob to get the plaintext key, then decrypts each row.

Or if you want to pass the key directly (for testing):

```bash
export ENCRYPTION_KEY_HEX=<64_char_hex_key>
python decrypt_client.py
```

## Files

| File | What it does |
|---|---|
| `encrypt_view.sql` | Creates the base table, encrypted view, and RBAC grants |
| `decrypt_client.py` | Calls KMS to get the key, queries the view, decrypts client-side |

## Production notes

- **Key in view DDL:** The hex key is visible in the view definition (`GET_DDL`). For production, use a [Snowflake external function + Lambda](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws) so the key never appears in SQL.
- **Key rotation:** Generate a new data key from the same CMK, update the view, re-encrypt or version your data.
- **If you don't need external decryption**, [dynamic data masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro) is simpler.

## References

- [ENCRYPT_RAW docs](https://docs.snowflake.com/en/sql-reference/functions/encrypt_raw)
- [AWS KMS GenerateDataKey](https://docs.aws.amazon.com/kms/latest/APIReference/API_GenerateDataKey.html)
- [AWS KMS Decrypt](https://docs.aws.amazon.com/kms/latest/APIReference/API_Decrypt.html)
- [Python AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.aead.AESGCM)
