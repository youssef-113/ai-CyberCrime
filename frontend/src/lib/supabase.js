/**
 * DEPRECATED: Direct Supabase client is no longer used in the frontend.
 * 
 * All database operations must go through the backend API endpoints:
 * - Authentication: /auth/login, /auth/register, /auth/verify
 * - Chat Sessions: /sessions, /chat endpoints
 * - Cases: /cases, /analyze endpoints
 * - Verifications: /verify, /verifications endpoints
 * - Data Queries: Backend API endpoints only
 * 
 * See /frontend/src/api/endpoints.js for all available API functions.
 * See /frontend/src/context/AuthContext.jsx for authentication context.
 */

console.warn(
  'DEPRECATED: Direct Supabase client access is no longer supported. All data must go through backend API endpoints.'
)

// Stub for backward compatibility (if imported anywhere)
export const supabase = null
export default supabase
