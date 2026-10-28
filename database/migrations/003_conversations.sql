BEGIN;
CREATE TABLE conversation_sessions (
    id uuid PRIMARY KEY,
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE conversation_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES conversation_sessions(id),
    request_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user','assistant')),
    content text NOT NULL CHECK (length(content) <= 16000),
    status text NOT NULL CHECK (status IN ('running','complete','failed')),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (session_id,request_id,role)
);
CREATE INDEX conversation_messages_session_idx ON conversation_messages(session_id,id);
CREATE TRIGGER conversation_sessions_updated BEFORE UPDATE ON conversation_sessions
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
COMMIT;
