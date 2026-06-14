# Database Schema — AI Cybercrime Evidence Builder

## Overview

The system uses **Supabase PostgreSQL** as the primary database, **ChromaDB** as the vector database for RAG embeddings, and **Redis** for caching and Celery task queue.

The authoritative DDL is in `scripts/supabase_schema.sql`. Run it in the Supabase SQL Editor to create all required tables.

---

## Database Technology

| Component        | Technology            | Purpose                          |
|------------------|-----------------------|----------------------------------|
| Primary Database | Supabase PostgreSQL   | Users, cases, chat, audit        |
| Vector Database  | ChromaDB              | Law article embeddings (RAG)     |
| Cache            | Redis (DB 0)          | Application + semantic cache     |
| Task Queue       | Redis (DB 1, DB 2)    | Celery broker + result backend   |
| Audit Store      | Supabase (or SQLite)  | Verification audit trail         |

---

## Tables

### 1. users

User accounts with authentication data.

```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

### 2. refresh_tokens

JWT refresh token store with revocation support.

```sql
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
```

### 3. cases

Case analysis records — stores pipeline results.

```sql
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
```

### 4. case_files

File metadata associated with cases.

```sql
-- Note: This table is referenced by the application code but may be created
-- dynamically. Check the application for exact schema.
```

### 5. chat_sessions

Chat session management with optional case linkage.

```sql
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
```

### 6. chat_messages

Individual chat messages with citations.

```sql
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
```

### 7. session_uploads

Files uploaded within a chat session.

```sql
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
```

### 8. verification_cases

Verification audit records.

```sql
CREATE TABLE IF NOT EXISTS verification_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    source_case_id VARCHAR(50) REFERENCES cases(case_id) ON DELETE SET NULL,
    session_id VARCHAR(100) REFERENCES chat_sessions(session_id) ON DELETE SET NULL,
    crime_type VARCHAR(50) NOT NULL,
    final_status VARCHAR(30),
    final_score INTEGER,
    total_rounds INTEGER,
    grade VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 9. verification_rounds

Individual verification rounds with attacker/judge data.

```sql
CREATE TABLE IF NOT EXISTS verification_rounds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id VARCHAR(100) NOT NULL REFERENCES verification_cases(case_id) ON DELETE CASCADE,
    round_num INTEGER NOT NULL,
    chat_message_id UUID REFERENCES chat_messages(id) ON DELETE SET NULL,
    attacker_prompt TEXT,
    attacker_response TEXT,
    attacker_challenges JSONB DEFAULT '[]',
    judge_prompt TEXT,
    judge_response TEXT,
    judge_status VARCHAR(30),
    judge_articles_cited JSONB DEFAULT '[]',
    judge_claims_to_drop JSONB DEFAULT '[]',
    judge_confidence REAL,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 10. audit_logs

Audit trail for all sensitive operations.

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    method VARCHAR(10),
    path TEXT,
    ip_address INET,
    user_agent TEXT,
    old_values JSONB,
    new_values JSONB,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 11. security_events

Security-related events for monitoring.

```sql
CREATE TABLE IF NOT EXISTS security_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    description TEXT,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 12. rate_limits

Rate limiting for API endpoints.

```sql
CREATE TABLE IF NOT EXISTS rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET,
    endpoint VARCHAR(100),
    window_seconds INTEGER DEFAULT 60,
    request_count INTEGER DEFAULT 0,
    max_requests INTEGER DEFAULT 100,
    window_start TIMESTAMPTZ DEFAULT NOW(),
    window_end TIMESTAMPTZ DEFAULT NOW() + INTERVAL '60 seconds',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 13. performance_metrics

System performance tracking.

```sql
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value REAL NOT NULL,
    unit VARCHAR(20),
    service_name VARCHAR(50),
    endpoint VARCHAR(100),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    labels JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 14. error_logs

Error tracking and debugging.

```sql
CREATE TABLE IF NOT EXISTS error_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(100),
    error_type VARCHAR(100),
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    service_name VARCHAR(50),
    endpoint VARCHAR(100),
    method VARCHAR(10),
    path TEXT,
    request_body JSONB,
    request_headers JSONB,
    severity VARCHAR(20) DEFAULT 'error',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Row Level Security (RLS)

User-scoped tables have RLS policies to isolate data:

```sql
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- Users see only their own data
CREATE POLICY "Users see own cases" ON cases
    FOR SELECT USING (user_id::text = (auth.jwt() -> 'sub')::text);
CREATE POLICY "Service full cases" ON cases
    FOR ALL USING (auth.role() = 'service_role');

-- (Similar policies for chat_sessions, chat_messages, session_uploads)
```

---

## Triggers

```sql
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
```

---

## Setup

Run `scripts/supabase_schema.sql` in the Supabase SQL Editor to create all required tables with indexes and RLS policies.
