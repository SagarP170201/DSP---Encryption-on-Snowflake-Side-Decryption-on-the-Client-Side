# Encryption on Snowflake Side, Decryption on the Client Side

**Pattern:** Snowflake `ENCRYPT_RAW` (AES-256-GCM) in a view + application-side decryption using the same key from AWS KMS.

## Architecture

```
┌─────────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   AWS KMS           │       │   Snowflake       │       │   Application   │
│                     │       │                   │       │                 │
│  CMK (master key)   │       │  CUSTOMER_BASE    │       │  Python client  │
│       │             │       │  (plaintext data) │       │                 │
│       ▼             │       │       │           │       │                 │
│  Data Key (32 bytes)│──────►│  CUSTOMER_ENC_V   │──────►│  AES-GCM        │
│  (AES-256)          │       │  (encrypted view) │       │  decrypt()      │
│                     │       │                   │       │       │         │
│  Secrets Manager    │       │  ENCRYPT_RAW()    │       │       ▼         │
│  (stores data key)  │───────────────────────────────────►  plaintext     │
└─────────────────────┘       └──────────────────┘       └─────────────────┘
```

**How it works:**
1. A 32-byte AES-256 data key is generated via AWS KMS
2. The same key is used in a Snowflake **view** to encrypt sensitive columns with `ENCRYPT_RAW`
3. The application retrieves the key from AWS KMS / Secrets Manager and decrypts client-side
4. The base table stays plaintext; only the view output is encrypted

## Prerequisites

| Requirement | Details |
|---|---|
| Snowflake account | With `ENCRYPT_RAW` support (all editions) |
| AWS account | With KMS and Secrets Manager access |
| Python 3.8+ | For the client-side scripts |
| AWS CLI | Configured with `aws configure` |
| Snowflake connection | Via `~/.snowflake/connections.toml` or env vars |

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Setup Guide (Step by Step)

### Step 1: Generate the encryption key in AWS KMS

This creates a 32-byte AES-256 data key using a KMS Customer Master Key (CMK) and stores it in AWS Secrets Manager.

```bash
python setup_kms_key.py
```

**What this does:**
1. Creates a KMS CMK (or uses an existing one you specify)
2. Calls `generate_data_key` to get a 32-byte plaintext + encrypted data key pair
3. Stores the plaintext key (hex-encoded) in AWS Secrets Manager as `snowflake/encrypt-raw/data-key`
4. Stores the encrypted (wrapped) key blob alongside it for future KMS re-derivation

**Manual alternative (AWS CLI):**

```bash
# Create a CMK
aws kms create-key --description "Snowflake ENCRYPT_RAW key" --key-spec SYMMETRIC_DEFAULT

# Generate a 256-bit data key (returns plaintext + encrypted blob)
aws kms generate-data-key \
  --key-id <YOUR_CMK_KEY_ID> \
  --key-spec AES_256

# Store the plaintext hex key in Secrets Manager
aws secretsmanager create-secret \
  --name snowflake/encrypt-raw/data-key \
  --secret-string '{"key_hex": "<64_CHAR_HEX_FROM_PLAINTEXT>"}'
```

### Step 2: Create the encrypted view in Snowflake

Open `encrypt_view.sql` and replace every `<32_BYTE_KEY_HEX>` with the 64-character hex key from Step 1.

Then run in Snowflake:

```sql
-- Run encrypt_view.sql in your Snowflake worksheet or via SnowSQL
-- This creates CUSTOMER_BASE (table) and CUSTOMER_ENC_V (encrypted view)
```

**Important:** In production, do NOT hardcode the key in SQL. Instead, use a Snowflake **external function** backed by an AWS Lambda that fetches the key from KMS at runtime. See [Advanced: External Function Pattern](#advanced-external-function-for-dynamic-key-retrieval) below.

### Step 3: Insert test data

```sql
INSERT INTO CUSTOMER_BASE VALUES
  (1, 'Alice', 'alice@example.com', '555-0101', '123 Main St', 'NID-1001'),
  (2, 'Bob',   'bob@example.com',   '555-0202', '456 Oak Ave',  'NID-2002');
```

### Step 4: Verify encryption

```sql
ALTER SESSION SET BINARY_OUTPUT_FORMAT = 'HEX';
SELECT * FROM CUSTOMER_ENC_V;
```

Each encrypted column returns a VARIANT:
```json
{
  "iv": "A1B2C3...",
  "ciphertext": "D4E5F6...",
  "tag": "789ABC..."
}
```

### Step 5: Decrypt from the application

```bash
# Set your Snowflake connection
export SNOWFLAKE_CONNECTION_NAME=default

# The script fetches the key from Secrets Manager automatically
python decrypt_client.py
```

Output:
```
--- Row ID: 1, Name: Alice ---
  EMAIL_ENC -> alice@example.com
  PHONE_ENC -> 555-0101
  ADDRESS_ENC -> 123 Main St
  NATIONAL_ID_ENC -> NID-1001
```

## File Structure

```
.
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── encrypt_view.sql       # Snowflake SQL: base table + encrypted view + RBAC
├── setup_kms_key.py       # AWS KMS key generation + Secrets Manager storage
└── decrypt_client.py      # Application-side decryption (fetches key from AWS)
```

## How ENCRYPT_RAW Works

```
ENCRYPT_RAW(value, key, iv, aad, method)
```

| Parameter | Value in this project | Purpose |
|---|---|---|
| `value` | `TO_BINARY(HEX_ENCODE(column), 'HEX')` | Converts VARCHAR to BINARY for encryption |
| `key` | `TO_BINARY('<hex_key>', 'HEX')` | 32-byte AES-256 key (same key the app uses) |
| `iv` | `NULL` | Snowflake generates a random 12-byte IV per call |
| `aad` | `NULL` | No additional authenticated data |
| `method` | `'AES-GCM'` | AES-256 in Galois/Counter Mode (authenticated encryption) |

**Returns:** VARIANT with `iv`, `ciphertext`, `tag` — all BINARY fields.

**Why AES-GCM?** It provides both encryption (confidentiality) and authentication (tamper detection via the tag). The tag ensures ciphertext hasn't been modified.

## AWS KMS Concepts

| Concept | Role in this project |
|---|---|
| **Customer Master Key (CMK)** | Never leaves KMS. Used to generate/wrap data keys. |
| **Data Key** | The 32-byte AES-256 key used in `ENCRYPT_RAW`. Generated by `generate_data_key`. |
| **Envelope Encryption** | CMK encrypts the data key; data key encrypts the data. Only the encrypted (wrapped) data key is stored long-term. |
| **Secrets Manager** | Convenience store for the plaintext hex key so the application can fetch it at runtime without calling KMS `decrypt` each time. |

**Key rotation:** Generate a new data key, re-create the view with the new key, update Secrets Manager. Old ciphertext must be decrypted with the old key first.

## Advanced: External Function for Dynamic Key Retrieval

Instead of hardcoding the key in SQL, use a Snowflake external function backed by AWS Lambda:

```
Snowflake VIEW  ──calls──►  External Function  ──calls──►  AWS Lambda  ──calls──►  KMS / Secrets Manager
                                (API Gateway)                                         │
                                                                                      ▼
                                                                              returns data key
```

This way the key never appears in Snowflake SQL. See:
- [Snowflake: Creating External Functions on AWS](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws)
- [Blog: External Functions for Custom Data Encryption](https://medium.com/snowflake/how-to-use-snowflake-external-functions-for-custom-data-encryption-ed04c56fc7a5)

## Alternatives to Consider

| Approach | When to use |
|---|---|
| **Dynamic Data Masking** (masking policies) | You want to hide/redact sensitive columns per role — no external decryption needed |
| **Row Access Policies** | You want to restrict which rows a role can see |
| **ENCRYPT_RAW** (this project) | Data must be decryptable **outside Snowflake** by an external application |
| **External Tokenization** (Protegrity, etc.) | Enterprise-grade tokenization with a dedicated vault |

## References

- [Snowflake ENCRYPT_RAW Documentation](https://docs.snowflake.com/en/sql-reference/functions/encrypt_raw)
- [Snowflake DECRYPT_RAW Documentation](https://docs.snowflake.com/en/sql-reference/functions/decrypt_raw)
- [Snowflake External Functions on AWS](https://docs.snowflake.com/en/sql-reference/external-functions-creating-aws)
- [AWS KMS GenerateDataKey API](https://docs.aws.amazon.com/kms/latest/APIReference/API_GenerateDataKey.html)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)
- [Python cryptography library (AESGCM)](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.aead.AESGCM)
