export const CRIME_TYPES = {
  blackmail: { en: 'Blackmail', ar: 'ابتزاز', color: 'danger' },
  scam: { en: 'Financial Scam', ar: 'احتيال مالي', color: 'warning' },
  fraud: { en: 'Fraud', ar: 'احتيال', color: 'warning' },
  threat: { en: 'Threat', ar: 'تهديد', color: 'danger' },
  defamation: { en: 'Defamation', ar: 'تشهير / قذف', color: 'warning' },
  identity_theft: { en: 'Identity Theft', ar: 'سرقة الهوية', color: 'danger' },
  privacy_violation: { en: 'Privacy Violation', ar: 'انتهاك خصوصية', color: 'primary' },
  phishing: { en: 'Phishing', ar: 'تصيد احتيالي', color: 'warning' },
  unknown: { en: 'Unknown', ar: 'غير محدد', color: 'neutral' },
}

export const EVIDENCE_GRADES = {
  STRONG: { label: 'Strong', labelAr: 'قوي', minScore: 75, color: 'success' },
  MEDIUM: { label: 'Medium', labelAr: 'متوسط', minScore: 45, color: 'warning' },
  WEAK: { label: 'Weak', labelAr: 'ضعيف', minScore: 0, color: 'danger' },
}

export const SCORE_WEIGHTS = {
  explicit_threat_found: { label: 'Explicit Threat', weight: 20 },
  financial_demand_found: { label: 'Financial Demand', weight: 20 },
  contact_identified: { label: 'Contact Identified', weight: 15 },
  multiple_evidence_files: { label: 'Multiple Evidence Files', weight: 15 },
  ocr_confidence_high: { label: 'OCR Confidence', weight: 15 },
  law_articles_retrieved: { label: 'Law Articles Retrieved', weight: 10 },
  date_timestamp_found: { label: 'Date/Timestamp', weight: 5 },
}

export const FILE_CONSTRAINTS = {
  MAX_FILES: 10,
  MAX_SIZE_MB: 10,
  ACCEPTED_TYPES: ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf'],
  ACCEPTED_EXTENSIONS: ['.png', '.jpg', '.jpeg', '.pdf'],
}

export const API_ENDPOINTS = {
  ANALYZE: '/analyze',
  ANALYZE_JSON: '/analyze/json',
  PDF: '/pdf',
  CHAT: '/chat',
  CASES: '/cases',
  HEALTH: '/health',
}

export const VERIFICATION_STATUS = {
  APPROVED: { label: 'Approved', color: 'success' },
  NEEDS_REVISION: { label: 'Needs Revision', color: 'warning' },
  NEEDS_USER_REVIEW: { label: 'Needs User Review', color: 'danger' },
}

export const NAV_ITEMS = [
  { path: '/', label: 'Home', icon: 'Home' },
  { path: '/dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
  { path: '/analyze', label: 'New Case', icon: 'Search' },
  { path: '/chatbot', label: 'Legal Chat', icon: 'MessageSquare' },
  { path: '/settings', label: 'Settings', icon: 'Settings' },
]

export const LANGUAGES = [
  { code: 'en', label: 'English', dir: 'ltr' },
  { code: 'ar', label: 'العربية', dir: 'rtl' },
]
