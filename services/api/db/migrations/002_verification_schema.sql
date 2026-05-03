-- Verification Service - Supabase Migration
-- Add verification_cases and verification_rounds tables
-- Run in Supabase SQL Editor

-- ============================================
-- Verification Cases Table
-- ============================================
CREATE TABLE IF NOT EXISTS verification_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id VARCHAR(100) UNIQUE NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_verification_cases_created_at ON verification_cases(created_at DESC);

-- ============================================
-- Verification Rounds Table
-- ============================================
CREATE TABLE IF NOT EXISTS verification_rounds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id VARCHAR(100) NOT NULL REFERENCES verification_cases(case_id) ON DELETE CASCADE,
    round_num INTEGER NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_verification_rounds_created_at ON verification_rounds(created_at);

-- ============================================
-- Auto-update trigger for verification_cases
-- ============================================
CREATE TRIGGER update_verification_cases_updated_at BEFORE UPDATE ON verification_cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- RLS Policies (service-role bypasses these)
-- ============================================
ALTER TABLE verification_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_rounds ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (used by backend)
CREATE POLICY verification_cases_service_access ON verification_cases
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY verification_rounds_service_access ON verification_rounds
    FOR ALL USING (true) WITH CHECK (true);
