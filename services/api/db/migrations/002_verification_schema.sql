-- Verification Service - Supabase Migration
-- Add verification_cases and verification_rounds tables
-- Run in Supabase SQL Editor

-- ============================================
-- Verification Cases Table
-- ============================================
-- Links to: users (who requested), cases (the main case), chat_sessions (session)
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
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_grade CHECK (grade IN ('STRONG', 'MEDIUM', 'WEAK') OR grade IS NULL),
    CONSTRAINT valid_status CHECK (
        final_status IN ('APPROVED', 'NEEDS_REVISION', 'NEEDS_USER_REVIEW', 'PENDING') OR final_status IS NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_verification_cases_case_id ON verification_cases(case_id);
CREATE INDEX IF NOT EXISTS idx_verification_cases_user_id ON verification_cases(user_id);
CREATE INDEX IF NOT EXISTS idx_verification_cases_source_case_id ON verification_cases(source_case_id);
CREATE INDEX IF NOT EXISTS idx_verification_cases_session_id ON verification_cases(session_id);
CREATE INDEX IF NOT EXISTS idx_verification_cases_created_at ON verification_cases(created_at DESC);

-- ============================================
-- Verification Rounds Table
-- ============================================
-- Links to chat_messages (optional - which message triggered this round)
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
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_round UNIQUE (case_id, round_num),
    CONSTRAINT valid_judge_status CHECK (
        judge_status IN ('APPROVED', 'NEEDS_REVISION', 'NEEDS_USER_REVIEW') OR judge_status IS NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_verification_rounds_case_id ON verification_rounds(case_id);
CREATE INDEX IF NOT EXISTS idx_verification_rounds_chat_message_id ON verification_rounds(chat_message_id);
CREATE INDEX IF NOT EXISTS idx_verification_rounds_created_at ON verification_rounds(created_at);

-- ============================================
-- Auto-update trigger for verification_cases
-- ============================================
CREATE TRIGGER update_verification_cases_updated_at BEFORE UPDATE ON verification_cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- RLS Policies (user-scoped)
-- ============================================
ALTER TABLE verification_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_rounds ENABLE ROW LEVEL SECURITY;

-- Users can see their own verification cases
CREATE POLICY verification_cases_user_access ON verification_cases
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)::UUID
        OR user_id IS NULL
    );

-- Rounds are accessible via case ownership
CREATE POLICY verification_rounds_user_access ON verification_rounds
    FOR ALL USING (
        case_id IN (
            SELECT case_id FROM verification_cases
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
            OR user_id IS NULL
        )
    );

-- ============================================
-- Audit View
-- ============================================
CREATE OR REPLACE VIEW verification_audit_trail AS
SELECT
    vc.case_id,
    vc.crime_type,
    vc.final_status,
    vc.final_score,
    vc.grade,
    vc.user_id,
    u.email AS user_email,
    u.full_name AS user_name,
    vc.source_case_id,
    vc.session_id,
    cs.title AS session_title,
    vr.round_num,
    vr.judge_status AS round_status,
    vr.judge_articles_cited,
    vr.judge_claims_to_drop,
    vr.judge_confidence,
    vr.latency_ms,
    vr.created_at AS round_created_at,
    vc.created_at AS case_created_at
FROM verification_cases vc
LEFT JOIN users u ON u.id = vc.user_id
LEFT JOIN chat_sessions cs ON cs.session_id = vc.session_id
LEFT JOIN LATERAL (
    SELECT * FROM verification_rounds vr
    WHERE vr.case_id = vc.case_id
    ORDER BY vr.round_num
) vr ON true
ORDER BY vc.created_at DESC, vr.round_num ASC;
