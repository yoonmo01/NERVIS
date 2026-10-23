-- Technical receipts, not user/business entities. Apply once to an existing DB.
BEGIN;
CREATE TABLE api_requests (
    request_id uuid PRIMARY KEY,
    operation text NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
