-- ============================================================
-- Encrypt-in-view with ENCRYPT_RAW (AES-256-GCM)
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
--    Replace <32_BYTE_KEY_HEX> with your 64-char hex string (32 bytes) from KMS.
--    3rd arg = NULL → Snowflake generates a random IV per call.
--    4th arg = NULL → no AAD (additional authenticated data).
CREATE OR REPLACE VIEW CUSTOMER_ENC_V AS
SELECT
  ID,
  NAME,

  CASE WHEN EMAIL IS NULL THEN NULL ELSE
    ENCRYPT_RAW(
      TO_BINARY(HEX_ENCODE(EMAIL), 'HEX'),
      TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
      NULL,
      NULL,
      'AES-GCM'
    )
  END AS EMAIL_ENC,

  CASE WHEN PHONE IS NULL THEN NULL ELSE
    ENCRYPT_RAW(
      TO_BINARY(HEX_ENCODE(PHONE), 'HEX'),
      TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
      NULL,
      NULL,
      'AES-GCM'
    )
  END AS PHONE_ENC,

  CASE WHEN ADDRESS IS NULL THEN NULL ELSE
    ENCRYPT_RAW(
      TO_BINARY(HEX_ENCODE(ADDRESS), 'HEX'),
      TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
      NULL,
      NULL,
      'AES-GCM'
    )
  END AS ADDRESS_ENC,

  CASE WHEN NATIONAL_ID IS NULL THEN NULL ELSE
    ENCRYPT_RAW(
      TO_BINARY(HEX_ENCODE(NATIONAL_ID), 'HEX'),
      TO_BINARY('<32_BYTE_KEY_HEX>', 'HEX'),
      NULL,
      NULL,
      'AES-GCM'
    )
  END AS NATIONAL_ID_ENC

FROM CUSTOMER_BASE;

-- 4. Access control
--    App role sees encrypted view only — not the base table.
--    Only crypto-admin level roles should have GET_DDL access on this view.
GRANT SELECT ON VIEW CUSTOMER_ENC_V TO ROLE APP_ROLE;
REVOKE SELECT ON TABLE CUSTOMER_BASE FROM ROLE APP_ROLE;

-- 5. Verify (after inserting test data)
-- INSERT INTO CUSTOMER_BASE VALUES (1, 'Alice', 'alice@test.com', '555-1234', '123 Main St', 'ID-9999');
-- INSERT INTO CUSTOMER_BASE VALUES (2, 'Bob', NULL, '555-5678', NULL, 'ID-8888');
-- SELECT * FROM CUSTOMER_ENC_V;
-- Each *_ENC column returns VARIANT: { "iv": "...", "ciphertext": "...", "tag": "..." }
-- NULL columns return NULL (no error)
