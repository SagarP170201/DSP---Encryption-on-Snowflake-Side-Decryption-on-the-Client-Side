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

### Step 1: Generate a key in AWS KMS (Console)

1. Go to **AWS Console → KMS → Customer managed keys → Create key**
2. Key type: **Symmetric**, Key usage: **Encrypt and decrypt** → Next
3. Give it an alias (e.g. `snowflake-encrypt-raw`) → finish creating
4. On the key detail page, click **Key actions → Generate data key without plaintext** — but we actually need the plaintext, so use this instead:
   - Go to **AWS CloudShell** (top-right bar in Console) and run:
     ```bash
     aws kms generate-data-key --key-id alias/snowflake-encrypt-raw --key-spec AES_256
     ```
   - Copy the `Plaintext` value from the output (base64-encoded)
   - Convert it to hex — in CloudShell:
     ```bash
     echo "<PASTE_PLAINTEXT_BASE64>" | base64 --decode | xxd -p -c 64
     ```
   - That 64-character hex string is your encryption key

5. Store it in **Secrets Manager**:
   - Go to **AWS Console → Secrets Manager → Store a new secret**
   - Secret type: **Other type of secret**
   - Key: `key_hex`, Value: paste the 64-char hex string
   - Secret name: `snowflake/encrypt-raw/data-key`
   - Click **Store**

### Step 2: Create the encrypted view in Snowflake

Edit `encrypt_view.sql` — replace every `<32_BYTE_KEY_HEX>` with the 64-char hex key from Step 1.

Then run it in a Snowflake worksheet. This creates:
- `CUSTOMER_BASE` — your table (plaintext, unchanged)
- `CUSTOMER_ENC_V` — a view that encrypts EMAIL, PHONE, ADDRESS, NATIONAL_ID on read

Test it:

```sql
INSERT INTO CUSTOMER_BASE VALUES (1, 'Alice', 'alice@example.com', '555-0101', '123 Main St', 'NID-1001');
ALTER SESSION SET BINARY_OUTPUT_FORMAT = 'HEX';
SELECT * FROM CUSTOMER_ENC_V;
-- Each encrypted column returns: { "iv": "...", "ciphertext": "...", "tag": "..." }
```

### Step 3: Decrypt in your app

```bash
pip install -r requirements.txt
export ENCRYPTION_KEY_HEX=<your_64_char_hex_key>
export SNOWFLAKE_CONNECTION_NAME=default
python decrypt_client.py
```

If the key is in Secrets Manager, you can skip `ENCRYPTION_KEY_HEX` — the script auto-fetches it.

## Files

| File | What it does |
|---|---|
| `encrypt_view.sql` | Creates the base table, encrypted view, and RBAC grants |
| `decrypt_client.py` | Queries the encrypted view and decrypts client-side |
| `setup_kms_key.py` | (Optional) Automates key generation via boto3 if you prefer CLI |

## Production notes

- **Don't hardcode the key in SQL.** Use a [Snowflake external function + AWS Lambda](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws) to fetch it at runtime.
- **Key rotation:** Generate a new key, update the view and Secrets Manager. Decrypt old data with the old key first.
- **If you don't need external decryption**, consider [dynamic data masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro) instead — it's simpler.

## References

- [ENCRYPT_RAW docs](https://docs.snowflake.com/en/sql-reference/functions/encrypt_raw)
- [AWS KMS GenerateDataKey](https://docs.aws.amazon.com/kms/latest/APIReference/API_GenerateDataKey.html)
- [Python AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.aead.AESGCM)
