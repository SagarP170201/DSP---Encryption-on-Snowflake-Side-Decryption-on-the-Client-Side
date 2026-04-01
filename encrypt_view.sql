-- ============================================================
-- OPTION A: Encrypt-in-view with ENCRYPT_RAW (AES-256-GCM)
-- ============================================================

-- 1. Set binary output to HEX for readability
ALTER SESSION SET BINARY_OUTPUT_FORMAT = 'HEX';

-- 2. Base table (unchanged — data stays plaintext at rest)
CREATE OR REPLACE TABLE CUSTOMER_BASE (
  ID            NUMBER,
  NAME          VARCHAR,
  EMAIL         VARCHAR,
  PHONE         VARCHAR,
  ADDRESS       VARCHAR,
  NATIONAL_ID   VARCHAR
);

-- 3. Encrypted view
--    Replace <32_BYTE_KEY_HEX> with your 64-char hex string (32 bytes).
--    This MUST be the same key stored in AWS KMS / Secrets Manager.
--    4th arg = NULL means no AAD (additional authenticated data).
--    3rd arg = NULL means Snowflake generates a random IV per call.
CREATE OR REPLACE VIEW CUSTOMER_ENC_V AS
SELECT
  ID,
  NAME,

  ENCRYPT_RAW(
    TO_BINARY(HEX_ENCODE(EMAIL), 'HEX'),
    TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
    NULL,                -- random IV
    NULL,                -- no AAD
    'AES-GCM'
  ) AS EMAIL_ENC,

  ENCRYPT_RAW(
    TO_BINARY(HEX_ENCODE(PHONE), 'HEX'),
    TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
    NULL,
    NULL,
    'AES-GCM'
  ) AS PHONE_ENC,

  ENCRYPT_RAW(
    TO_BINARY(HEX_ENCODE(ADDRESS), 'HEX'),
    TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
    NULL,
    NULL,
    'AES-GCM'
  ) AS ADDRESS_ENC,

  ENCRYPT_RAW(
    TO_BINARY(HEX_ENCODE(NATIONAL_ID), 'HEX'),
    TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
    NULL,
    NULL,
    'AES-GCM'
  ) AS NATIONAL_ID_ENC

FROM CUSTOMER_BASE;

-- 4. Access control
GRANT SELECT ON VIEW CUSTOMER_ENC_V TO ROLE APP_ROLE;
REVOKE SELECT ON TABLE CUSTOMER_BASE FROM ROLE APP_ROLE;

-- 5. Verify (after inserting test data)
-- INSERT INTO CUSTOMER_BASE VALUES (1, 'Alice', 'alice@test.com', '555-1234', '123 Main St', 'ID-9999');
-- SELECT * FROM CUSTOMER_ENC_V;
-- Each *_ENC column returns VARIANT: { "iv": "...", "ciphertext": "...", "tag": "..." }
