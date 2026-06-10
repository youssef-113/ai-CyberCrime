-- Complete Database Schema for Cybercrime AI System
-- This is a consolidated schema file combining all migrations
-- Run this in Supabase SQL Editor to create the complete database structure

-- ============================================
-- Enable Required Extensions
-- ============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE public.users (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  email character varying NOT NULL UNIQUE CHECK (email::text ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'::text),
  hashed_password character varying NOT NULL,
  full_name character varying,
  is_active boolean DEFAULT true,
  is_verified boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  phone character varying CHECK (phone::text ~ '^\+?[0-9]{10,15}$'::text OR phone IS NULL),
  last_login_at timestamp with time zone,
  failed_login_attempts integer DEFAULT 0,
  locked_until timestamp with time zone,
  password_changed_at timestamp with time zone DEFAULT now(),
  mfa_enabled boolean DEFAULT false,
  mfa_secret character varying,
  recovery_codes jsonb DEFAULT '[]'::jsonb,
  language character varying DEFAULT 'ar'::character varying,
  timezone character varying DEFAULT 'Africa/Cairo'::character varying,
  notification_preferences jsonb DEFAULT '{"push": false, "email": true}'::jsonb,
  deleted_at timestamp with time zone,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);
CREATE TABLE public.refresh_tokens (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  token_hash character varying NOT NULL,
  expires_at timestamp with time zone NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  revoked_at timestamp with time zone,
  CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id),
  CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.cases (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  case_id character varying NOT NULL UNIQUE,
  user_id uuid NOT NULL,
  status character varying DEFAULT 'processing'::character varying CHECK (status::text = ANY (ARRAY['processing'::character varying, 'completed'::character varying, 'failed'::character varying, 'pending'::character varying]::text[])),
  files_count integer DEFAULT 0,
  result jsonb,
  error text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  crime_type character varying,
  priority character varying DEFAULT 'normal'::character varying CHECK (priority::text = ANY (ARRAY['low'::character varying, 'normal'::character varying, 'urgent'::character varying, 'critical'::character varying]::text[])),
  score integer,
  grade character varying CHECK (grade::text = ANY (ARRAY['A'::character varying, 'B'::character varying, 'C'::character varying, 'D'::character varying, 'F'::character varying]::text[]) OR grade IS NULL),
  verification_case_id character varying,
  completed_at timestamp with time zone,
  CONSTRAINT cases_pkey PRIMARY KEY (id),
  CONSTRAINT cases_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
  CONSTRAINT cases_verification_case_id_fkey FOREIGN KEY (verification_case_id) REFERENCES public.verification_cases(case_id) ON DELETE SET NULL
);
CREATE TABLE public.chat_sessions (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  session_id character varying NOT NULL UNIQUE,
  user_id uuid NOT NULL,
  title character varying,
  case_context jsonb,
  language character varying DEFAULT 'ar'::character varying,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  linked_case_id character varying,
  model_used character varying,
  temperature real DEFAULT 0.3,
  max_tokens integer DEFAULT 800,
  is_archived boolean DEFAULT false,
  is_pinned boolean DEFAULT false,
  message_count integer DEFAULT 0,
  last_message_at timestamp with time zone,
  archived_at timestamp with time zone,
  CONSTRAINT chat_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT chat_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.chat_messages (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  session_id character varying NOT NULL,
  role character varying NOT NULL CHECK (role::text = ANY (ARRAY['user'::character varying, 'assistant'::character varying, 'system'::character varying]::text[])),
  content text NOT NULL,
  citations jsonb DEFAULT '[]'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  user_id uuid,
  confidence_score real,
  model_used character varying,
  tokens_used integer,
  latency_ms integer,
  processing_steps jsonb DEFAULT '{}'::jsonb,
  error_message text,
  CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
  CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(session_id),
  CONSTRAINT chat_messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.verification_cases (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  case_id character varying NOT NULL UNIQUE,
  user_id uuid,
  source_case_id character varying,
  session_id character varying,
  crime_type character varying NOT NULL,
  final_status character varying CHECK ((final_status::text = ANY (ARRAY['APPROVED'::character varying, 'NEEDS_REVISION'::character varying, 'NEEDS_USER_REVIEW'::character varying, 'PENDING'::character varying]::text[])) OR final_status IS NULL),
  final_score integer,
  total_rounds integer,
  grade character varying CHECK ((grade::text = ANY (ARRAY['STRONG'::character varying, 'MEDIUM'::character varying, 'WEAK'::character varying]::text[])) OR grade IS NULL),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT verification_cases_pkey PRIMARY KEY (id),
  CONSTRAINT verification_cases_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT verification_cases_source_case_id_fkey FOREIGN KEY (source_case_id) REFERENCES public.cases(case_id),
  CONSTRAINT verification_cases_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(session_id)
);
CREATE TABLE public.verification_rounds (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  case_id character varying NOT NULL,
  round_num integer NOT NULL,
  chat_message_id uuid,
  attacker_prompt text,
  attacker_response text,
  attacker_challenges jsonb DEFAULT '[]'::jsonb,
  judge_prompt text,
  judge_response text,
  judge_status character varying CHECK ((judge_status::text = ANY (ARRAY['APPROVED'::character varying, 'NEEDS_REVISION'::character varying, 'NEEDS_USER_REVIEW'::character varying]::text[])) OR judge_status IS NULL),
  judge_articles_cited jsonb DEFAULT '[]'::jsonb,
  judge_claims_to_drop jsonb DEFAULT '[]'::jsonb,
  judge_confidence real,
  latency_ms integer,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT verification_rounds_pkey PRIMARY KEY (id),
  CONSTRAINT verification_rounds_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.verification_cases(case_id),
  CONSTRAINT verification_rounds_chat_message_id_fkey FOREIGN KEY (chat_message_id) REFERENCES public.chat_messages(id)
);
CREATE TABLE public.user_sessions (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  session_token character varying NOT NULL UNIQUE,
  ip_address inet,
  user_agent text,
  device_type character varying,
  location_country character varying,
  location_city character varying,
  is_active boolean DEFAULT true,
  last_activity_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT user_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.user_preferences (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL UNIQUE,
  default_language character varying DEFAULT 'ar'::character varying,
  chat_history_limit integer DEFAULT 20,
  auto_summarize boolean DEFAULT true,
  retrieval_top_k integer DEFAULT 5,
  enable_reranking boolean DEFAULT true,
  theme character varying DEFAULT 'dark'::character varying,
  font_size integer DEFAULT 16,
  email_notifications boolean DEFAULT true,
  push_notifications boolean DEFAULT false,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT user_preferences_pkey PRIMARY KEY (id),
  CONSTRAINT user_preferences_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.documents (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  document_id character varying NOT NULL UNIQUE,
  user_id uuid,
  title character varying,
  description text,
  document_type character varying,
  source text,
  raw_content text,
  processed_content text,
  language character varying DEFAULT 'ar'::character varying,
  processing_status character varying DEFAULT 'pending'::character varying CHECK (processing_status::text = ANY (ARRAY['pending'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying]::text[])),
  chunk_count integer DEFAULT 0,
  embedding_model character varying,
  law_name character varying,
  article_number character varying,
  crime_types jsonb DEFAULT '[]'::jsonb,
  keywords jsonb DEFAULT '[]'::jsonb,
  penalty_ar text,
  metadata jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  indexed_at timestamp with time zone,
  CONSTRAINT documents_pkey PRIMARY KEY (id),
  CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.document_chunks (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  chunk_id character varying NOT NULL UNIQUE,
  document_id uuid NOT NULL,
  chunk_text text NOT NULL,
  chunk_index integer NOT NULL,
  chunk_size integer,
  embedding_model character varying,
  embedding_vector USER-DEFINED,
  embedding_id character varying,
  metadata jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT document_chunks_pkey PRIMARY KEY (id),
  CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id)
);
CREATE TABLE public.retrieval_logs (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid,
  session_id character varying,
  query_text text NOT NULL,
  query_type character varying,
  transformed_query text,
  top_k integer DEFAULT 5,
  reranking_enabled boolean DEFAULT true,
  filters jsonb,
  chunks_retrieved integer,
  chunks_after_reranking integer,
  retrieval_time_ms integer,
  cache_hit boolean DEFAULT false,
  cache_key character varying,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT retrieval_logs_pkey PRIMARY KEY (id),
  CONSTRAINT retrieval_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
  CONSTRAINT retrieval_logs_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(session_id)
);
CREATE TABLE public.semantic_cache (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  cache_key character varying NOT NULL UNIQUE,
  query_embedding USER-DEFINED,
  query_text text,
  response_text text NOT NULL,
  citations jsonb DEFAULT '[]'::jsonb,
  hit_count integer DEFAULT 0,
  last_hit_at timestamp with time zone,
  ttl_seconds integer DEFAULT 3600,
  expires_at timestamp with time zone NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT semantic_cache_pkey PRIMARY KEY (id)
);
CREATE TABLE public.audit_logs (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid,
  session_id character varying,
  action character varying NOT NULL,
  entity_type character varying,
  entity_id character varying,
  method character varying,
  path text,
  ip_address inet,
  user_agent text,
  old_values jsonb,
  new_values jsonb,
  status character varying DEFAULT 'success'::character varying CHECK (status::text = ANY (ARRAY['success'::character varying, 'failure'::character varying, 'blocked'::character varying]::text[])),
  error_message text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT audit_logs_pkey PRIMARY KEY (id),
  CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.security_events (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid,
  event_type character varying NOT NULL,
  severity character varying DEFAULT 'info'::character varying CHECK (severity::text = ANY (ARRAY['info'::character varying, 'warning'::character varying, 'critical'::character varying, 'emergency'::character varying]::text[])),
  description text,
  ip_address inet,
  user_agent text,
  location_country character varying,
  metadata jsonb,
  resolved boolean DEFAULT false,
  resolved_at timestamp with time zone,
  resolution_notes text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT security_events_pkey PRIMARY KEY (id),
  CONSTRAINT security_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.rate_limits (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid,
  ip_address inet,
  endpoint character varying,
  window_seconds integer DEFAULT 60,
  request_count integer DEFAULT 0,
  max_requests integer DEFAULT 100,
  window_start timestamp with time zone DEFAULT now(),
  window_end timestamp with time zone DEFAULT (now() + '00:01:00'::interval),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT rate_limits_pkey PRIMARY KEY (id),
  CONSTRAINT rate_limits_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.case_files (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  case_id character varying NOT NULL,
  user_id uuid,
  file_name character varying NOT NULL,
  file_type character varying,
  file_size integer,
  file_path text,
  storage_type character varying DEFAULT 'local'::character varying,
  ocr_status character varying DEFAULT 'pending'::character varying CHECK (ocr_status::text = ANY (ARRAY['pending'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying]::text[])),
  ocr_confidence real,
  extracted_text text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT case_files_pkey PRIMARY KEY (id),
  CONSTRAINT case_files_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(case_id) ON DELETE CASCADE,
  CONSTRAINT case_files_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);
CREATE TABLE public.session_uploads (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  session_id character varying NOT NULL,
  user_id uuid,
  file_name character varying NOT NULL,
  file_type character varying,
  file_size integer,
  file_path text,
  processing_status character varying DEFAULT 'pending'::character varying CHECK (processing_status::text = ANY (ARRAY['pending'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying]::text[])),
  indexed_chunks integer DEFAULT 0,
  error_message text,
  metadata jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT session_uploads_pkey PRIMARY KEY (id),
  CONSTRAINT session_uploads_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(session_id) ON DELETE CASCADE,
  CONSTRAINT session_uploads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);
CREATE TABLE public.chat_summaries (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  session_id character varying NOT NULL,
  summary_text text NOT NULL,
  summary_type character varying DEFAULT 'auto'::character varying CHECK (summary_type::text = ANY (ARRAY['auto'::character varying, 'manual'::character varying]::text[])),
  message_range_start integer,
  message_range_end integer,
  model_used character varying,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT chat_summaries_pkey PRIMARY KEY (id),
  CONSTRAINT chat_summaries_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(session_id) ON DELETE CASCADE
);
CREATE TABLE public.performance_metrics (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  metric_name character varying NOT NULL,
  metric_value real NOT NULL,
  unit character varying,
  service_name character varying,
  endpoint character varying,
  user_id uuid,
  labels jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT performance_metrics_pkey PRIMARY KEY (id),
  CONSTRAINT performance_metrics_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);
CREATE TABLE public.error_logs (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid,
  session_id character varying,
  error_type character varying,
  error_message text NOT NULL,
  stack_trace text,
  service_name character varying,
  endpoint character varying,
  method character varying,
  path text,
  request_body jsonb,
  request_headers jsonb,
  severity character varying DEFAULT 'error'::character varying CHECK (severity::text = ANY (ARRAY['debug'::character varying, 'info'::character varying, 'warning'::character varying, 'error'::character varying, 'critical'::character varying]::text[])),
  resolved boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT error_logs_pkey PRIMARY KEY (id),
  CONSTRAINT error_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Users indexes
CREATE INDEX idx_users_email ON public.users(email);
CREATE INDEX idx_users_is_active ON public.users(is_active);
CREATE INDEX idx_users_deleted_at ON public.users(deleted_at) WHERE deleted_at IS NOT NULL;

-- Refresh tokens indexes
CREATE INDEX idx_refresh_tokens_user_id ON public.refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON public.refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON public.refresh_tokens(expires_at);

-- Cases indexes
CREATE INDEX idx_cases_user_id ON public.cases(user_id);
CREATE INDEX idx_cases_case_id ON public.cases(case_id);
CREATE INDEX idx_cases_created_at ON public.cases(created_at DESC);
CREATE INDEX idx_cases_status ON public.cases(status);
CREATE INDEX idx_cases_crime_type ON public.cases(crime_type);
CREATE INDEX idx_cases_user_status ON public.cases(user_id, status, created_at DESC);
CREATE INDEX idx_cases_crime_status ON public.cases(crime_type, status);
CREATE INDEX idx_cases_verification_case_id ON public.cases(verification_case_id);

-- Chat sessions indexes
CREATE INDEX idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_session_id ON public.chat_sessions(session_id);
CREATE INDEX idx_chat_sessions_linked_case_id ON public.chat_sessions(linked_case_id);
CREATE INDEX idx_chat_sessions_is_archived ON public.chat_sessions(is_archived);
CREATE INDEX idx_chat_sessions_last_message_at ON public.chat_sessions(last_message_at DESC);
CREATE INDEX idx_chat_sessions_user_archived ON public.chat_sessions(user_id, is_archived, last_message_at DESC);

-- Chat messages indexes
CREATE INDEX idx_chat_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX idx_chat_messages_user_id ON public.chat_messages(user_id);
CREATE INDEX idx_chat_messages_created_at ON public.chat_messages(created_at);
CREATE INDEX idx_chat_messages_role ON public.chat_messages(role);

-- Verification cases indexes
CREATE INDEX idx_verification_cases_case_id ON public.verification_cases(case_id);
CREATE INDEX idx_verification_cases_user_id ON public.verification_cases(user_id);
CREATE INDEX idx_verification_cases_source_case_id ON public.verification_cases(source_case_id);
CREATE INDEX idx_verification_cases_session_id ON public.verification_cases(session_id);
CREATE INDEX idx_verification_cases_created_at ON public.verification_cases(created_at DESC);
CREATE INDEX idx_verification_user_status ON public.verification_cases(user_id, final_status, created_at DESC);

-- Verification rounds indexes
CREATE INDEX idx_verification_rounds_case_id ON public.verification_rounds(case_id);
CREATE INDEX idx_verification_rounds_chat_message_id ON public.verification_rounds(chat_message_id);
CREATE INDEX idx_verification_rounds_created_at ON public.verification_rounds(created_at);

-- User sessions indexes
CREATE INDEX idx_user_sessions_user_id ON public.user_sessions(user_id);
CREATE INDEX idx_user_sessions_token ON public.user_sessions(session_token);
CREATE INDEX idx_user_sessions_is_active ON public.user_sessions(is_active);

-- User preferences indexes
CREATE INDEX idx_user_preferences_user_id ON public.user_preferences(user_id);

-- Documents indexes
CREATE INDEX idx_documents_document_id ON public.documents(document_id);
CREATE INDEX idx_documents_user_id ON public.documents(user_id);
CREATE INDEX idx_documents_document_type ON public.documents(document_type);
CREATE INDEX idx_documents_law_name ON public.documents(law_name);
CREATE INDEX idx_documents_crime_types ON public.documents USING GIN(crime_types);
CREATE INDEX idx_documents_keywords ON public.documents USING GIN(keywords);
CREATE INDEX idx_documents_type_status ON public.documents(document_type, processing_status);
CREATE INDEX idx_documents_content_fts ON public.documents USING GIN(to_tsvector('arabic', processed_content));
CREATE INDEX idx_documents_title_fts ON public.documents USING GIN(to_tsvector('arabic', title));

-- Document chunks indexes
CREATE INDEX idx_document_chunks_chunk_id ON public.document_chunks(chunk_id);
CREATE INDEX idx_document_chunks_document_id ON public.document_chunks(document_id);
CREATE INDEX idx_document_chunks_embedding_id ON public.document_chunks(embedding_id);
CREATE INDEX idx_document_chunks_embedding_vector ON public.document_chunks USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);

-- Retrieval logs indexes
CREATE INDEX idx_retrieval_logs_user_id ON public.retrieval_logs(user_id);
CREATE INDEX idx_retrieval_logs_session_id ON public.retrieval_logs(session_id);
CREATE INDEX idx_retrieval_logs_created_at ON public.retrieval_logs(created_at DESC);
CREATE INDEX idx_retrieval_logs_cache_hit ON public.retrieval_logs(cache_hit);

-- Semantic cache indexes
CREATE INDEX idx_semantic_cache_cache_key ON public.semantic_cache(cache_key);
CREATE INDEX idx_semantic_cache_expires_at ON public.semantic_cache(expires_at);
CREATE INDEX idx_semantic_cache_query_embedding ON public.semantic_cache USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);

-- Audit logs indexes
CREATE INDEX idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON public.audit_logs(action);
CREATE INDEX idx_audit_logs_entity ON public.audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON public.audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_status ON public.audit_logs(status);

-- Security events indexes
CREATE INDEX idx_security_events_user_id ON public.security_events(user_id);
CREATE INDEX idx_security_events_event_type ON public.security_events(event_type);
CREATE INDEX idx_security_events_severity ON public.security_events(severity);
CREATE INDEX idx_security_events_resolved ON public.security_events(resolved);
CREATE INDEX idx_security_events_created_at ON public.security_events(created_at DESC);

-- Rate limits indexes
CREATE INDEX idx_rate_limits_user_id ON public.rate_limits(user_id);
CREATE INDEX idx_rate_limits_ip_address ON public.rate_limits(ip_address);
CREATE INDEX idx_rate_limits_endpoint ON public.rate_limits(endpoint);
CREATE INDEX idx_rate_limits_window_end ON public.rate_limits(window_end);

-- Case files indexes
CREATE INDEX idx_case_files_case_id ON public.case_files(case_id);
CREATE INDEX idx_case_files_user_id ON public.case_files(user_id);
CREATE INDEX idx_case_files_ocr_status ON public.case_files(ocr_status);

-- Session uploads indexes
CREATE INDEX idx_session_uploads_session_id ON public.session_uploads(session_id);
CREATE INDEX idx_session_uploads_user_id ON public.session_uploads(user_id);
CREATE INDEX idx_session_uploads_processing_status ON public.session_uploads(processing_status);

-- Chat summaries indexes
CREATE INDEX idx_chat_summaries_session_id ON public.chat_summaries(session_id);

-- Performance metrics indexes
CREATE INDEX idx_performance_metrics_metric_name ON public.performance_metrics(metric_name);
CREATE INDEX idx_performance_metrics_service_name ON public.performance_metrics(service_name);
CREATE INDEX idx_performance_metrics_created_at ON public.performance_metrics(created_at DESC);

-- Error logs indexes
CREATE INDEX idx_error_logs_user_id ON public.error_logs(user_id);
CREATE INDEX idx_error_logs_error_type ON public.error_logs(error_type);
CREATE INDEX idx_error_logs_service_name ON public.error_logs(service_name);
CREATE INDEX idx_error_logs_severity ON public.error_logs(severity);
CREATE INDEX idx_error_logs_resolved ON public.error_logs(resolved);
CREATE INDEX idx_error_logs_created_at ON public.error_logs(created_at DESC);

-- ============================================
-- Database Functions
-- ============================================

-- Auto-update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Session message counter
CREATE OR REPLACE FUNCTION update_session_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE public.chat_sessions 
        SET message_count = message_count + 1,
            last_message_at = NOW()
        WHERE session_id = NEW.session_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Cleanup old data
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    DELETE FROM public.users 
    WHERE deleted_at < NOW() - INTERVAL '30 days';
    
    DELETE FROM public.audit_logs 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    DELETE FROM public.security_events 
    WHERE created_at < NOW() - INTERVAL '180 days';
    
    DELETE FROM public.semantic_cache 
    WHERE expires_at < NOW();
    
    DELETE FROM public.rate_limits 
    WHERE window_end < NOW();
END;
$$ LANGUAGE plpgsql;

-- Anonymize user data (GDPR compliance)
CREATE OR REPLACE FUNCTION anonymize_user(user_uuid UUID)
RETURNS void AS $$
BEGIN
    UPDATE public.users SET
        email = 'deleted_' || id::text || '@deleted.local',
        hashed_password = '',
        full_name = 'Deleted User',
        phone = NULL,
        mfa_secret = NULL,
        recovery_codes = '[]',
        deleted_at = NOW()
    WHERE id = user_uuid;
    
    UPDATE public.chat_sessions SET title = 'Deleted Session' 
    WHERE user_id = user_uuid;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Triggers
-- ============================================

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_sessions_updated_at BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON public.documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cases_updated_at BEFORE UPDATE ON public.cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_verification_cases_updated_at BEFORE UPDATE ON public.verification_cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON public.user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_case_files_updated_at BEFORE UPDATE ON public.case_files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_session_uploads_updated_at BEFORE UPDATE ON public.session_uploads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Apply session message counter trigger
CREATE TRIGGER update_chat_session_message_count 
    AFTER INSERT ON public.chat_messages
    FOR EACH ROW EXECUTE FUNCTION update_session_message_count();

-- ============================================
-- Row Level Security (RLS) Policies
-- ============================================

-- Enable RLS on all user-scoped tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refresh_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verification_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verification_rounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.retrieval_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.semantic_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.error_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.session_uploads ENABLE ROW LEVEL SECURITY;

-- Users can only access their own data
CREATE POLICY users_self_access ON public.users
    FOR ALL USING (id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY refresh_tokens_user_access ON public.refresh_tokens
    FOR ALL USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY user_sessions_user_access ON public.user_sessions
    FOR ALL USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY user_preferences_user_access ON public.user_preferences
    FOR ALL USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Chat sessions and messages
CREATE POLICY chat_sessions_user_access ON public.chat_sessions
    FOR ALL USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY chat_messages_user_access ON public.chat_messages
    FOR ALL USING (
        session_id IN (
            SELECT session_id FROM public.chat_sessions 
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
        OR user_id = current_setting('app.current_user_id', true)::UUID
    );

-- Cases and files
CREATE POLICY cases_user_access ON public.cases
    FOR ALL USING (user_id = current_setting('app.current_user_id', true)::UUID);

CREATE POLICY case_files_user_access ON public.case_files
    FOR ALL USING (
        case_id IN (
            SELECT case_id FROM public.cases 
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
    );

-- Documents (user-owned or system docs)
CREATE POLICY documents_user_access ON public.documents
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)::UUID 
        OR user_id IS NULL
    );

-- Document chunks via document ownership
CREATE POLICY document_chunks_user_access ON public.document_chunks
    FOR ALL USING (
        document_id IN (
            SELECT id FROM public.documents
            WHERE user_id = current_setting('app.current_user_id', true)::UUID 
            OR user_id IS NULL
        )
    );

-- Verification cases
CREATE POLICY verification_cases_user_access ON public.verification_cases
    FOR ALL USING (
        user_id = current_setting('app.current_user_id', true)::UUID 
        OR user_id IS NULL
    );

-- Verification rounds via case ownership
CREATE POLICY verification_rounds_user_access ON public.verification_rounds
    FOR ALL USING (
        case_id IN (
            SELECT case_id FROM public.verification_cases
            WHERE user_id = current_setting('app.current_user_id', true)::UUID 
            OR user_id IS NULL
        )
    );

-- Audit logs (users can see their own)
CREATE POLICY audit_logs_user_access ON public.audit_logs
    FOR SELECT USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Security events (users can see their own)
CREATE POLICY security_events_user_access ON public.security_events
    FOR SELECT USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Rate limits (system only)
CREATE POLICY rate_limits_system_access ON public.rate_limits
    FOR ALL USING (FALSE);

-- Retrieval logs
CREATE POLICY retrieval_logs_user_access ON public.retrieval_logs
    FOR ALL USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Semantic cache (shared)
CREATE POLICY semantic_cache_user_access ON public.semantic_cache
    FOR ALL USING (TRUE);

-- Chat summaries via session ownership
CREATE POLICY chat_summaries_user_access ON public.chat_summaries
    FOR ALL USING (
        session_id IN (
            SELECT session_id FROM public.chat_sessions 
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
    );

-- Performance metrics
CREATE POLICY performance_metrics_user_access ON public.performance_metrics
    FOR SELECT USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Error logs
CREATE POLICY error_logs_user_access ON public.error_logs
    FOR SELECT USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Session uploads via session ownership
CREATE POLICY session_uploads_user_access ON public.session_uploads
    FOR ALL USING (
        session_id IN (
            SELECT session_id FROM public.chat_sessions 
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
    );