-- ============================================================
-- AI Cybercrime Evidence Builder - Supabase Schema
-- Run this in Supabase SQL Editor to create all required tables
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ════════════════════════════════════════════════════════════
--  USERS TABLE
-- ════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'user',
    language TEXT DEFAULT 'ar',
    timezone TEXT DEFAULT 'Africa/Cairo',
    notification_preferences JSONB DEFAULT '{}',
    mfa_enabled BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ════════════════════════════════════════════════════════════
--  REFRESH TOKENS TABLE
-- ════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- ════════════════════════════════════════════════════════════
--  CASES TABLE
-- ════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id TEXT UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'processing',
    files_count INTEGER DEFAULT 0,
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_user ON cases(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_case_id ON cases(case_id);

-- ════════════════════════════════════════════════════════════
--  CHAT SESSIONS TABLE
-- ════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    case_context JSONB,
    language TEXT DEFAULT 'ar',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);

-- ════════════════════════════════════════════════════════════
--  CHAT MESSAGES TABLE
-- ════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id);

-- ════════════════════════════════════════════════════════════
--  SESSION UPLOADS TABLE
-- ════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS session_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_type TEXT,
    indexed_chunks INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_uploads_session ON session_uploads(session_id);

-- ════════════════════════════════════════════════════════════
--  ROW LEVEL SECURITY (RLS) - User Isolation
-- ════════════════════════════════════════════════════════════

-- Enable RLS on all user-scoped tables
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (used by backend with SERVICE_KEY)
-- These policies allow the backend (using service_role key) full access
-- while users can only see their own data via anon key

-- Cases: users see only their own
CREATE POLICY "Users see own cases" ON cases
    FOR SELECT USING (user_id::text = (auth.jwt() -> 'sub')::text);
CREATE POLICY "Service full cases" ON cases
    FOR ALL USING (auth.role() = 'service_role');

-- Chat sessions: users see only their own
CREATE POLICY "Users see own sessions" ON chat_sessions
    FOR SELECT USING (user_id::text = (auth.jwt() -> 'sub')::text);
CREATE POLICY "Service full sessions" ON chat_sessions
    FOR ALL USING (auth.role() = 'service_role');

-- Chat messages: accessible via session ownership
CREATE POLICY "Users see own messages" ON chat_messages
    FOR SELECT USING (
        session_id IN (
            SELECT session_id FROM chat_sessions
            WHERE user_id::text = (auth.jwt() -> 'sub')::text
        )
    );
CREATE POLICY "Service full messages" ON chat_messages
    FOR ALL USING (auth.role() = 'service_role');

-- Session uploads: accessible via session ownership
CREATE POLICY "Users see own uploads" ON session_uploads
    FOR SELECT USING (
        session_id IN (
            SELECT session_id FROM chat_sessions
            WHERE user_id::text = (auth.jwt() -> 'sub')::text
        )
    );
CREATE POLICY "Service full uploads" ON session_uploads
    FOR ALL USING (auth.role() = 'service_role');

-- Refresh tokens: only service role
CREATE POLICY "Service full tokens" ON refresh_tokens
    FOR ALL USING (auth.role() = 'service_role');

-- ════════════════════════════════════════════════════════════
--  UPDATED_AT TRIGGER
-- ════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_cases_updated_at BEFORE UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
