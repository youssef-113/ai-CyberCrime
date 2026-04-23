# API Integration Summary

## Backend Services & Endpoints

### 1. API Gateway (Port 8000) - Main Orchestrator
- `GET /` - Root info
- `GET /health` - Health check for all services
- `POST /analyze` - Start async analysis pipeline
- `POST /analyze/json` - Run full pipeline and return JSON (sync)
- `GET /cases` - List all cases
- `GET /cases/{case_id}` - Get case status and results
- `GET /pdf/{case_id}` - Download generated PDF

### 2. OCR Service (Port 8001)
- `GET /health` - Health check
- `POST /extract` - Extract text and entities from image/PDF/text

### 3. Classifier Service (Port 8002)
- `GET /health` - Health check
- `POST /classify` - Classify crime type using LLM

### 4. RAG Service (Port 8003)
- `GET /health` - Health check
- `POST /retrieve` - Retrieve relevant law articles
- `POST /index` - Index law articles

### 5. Verification Service (Port 8004)
- `GET /health` - Health check
- `POST /verify` - Run multi-agent verification

### 6. PDF Generation Service (Port 8005)
- `GET /health` - Health check
- `POST /generate` - Generate complaint PDF

### 7. Chatbot Service (Port 8006)
- `GET /health` - Health check
- `POST /chat` - Send a message to the legal chatbot
- `POST /chat/reset` - Clear all history for a session
- `GET /chat/history` - Get full conversation history for a session
- `GET /sessions` - List all active sessions
- `POST /chat/pdf_trigger` - Trigger PDF generation from chat context

## Frontend API Integration

### API Endpoints (`frontend/src/api/endpoints.js`)
All backend endpoints are now integrated:

```javascript
// Analysis
- analyzeEvidence(files, onProgress)          // POST /analyze
- analyzeEvidenceJson(files, onProgress)       // POST /analyze/json

// Cases
- getCaseHistory(params)                       // GET /cases
- getCaseById(caseId)                           // GET /cases/{case_id}
- downloadPdf(caseId)                          // GET /pdf/{case_id}

// Chatbot
- sendChatMessage(sessionId, message, context)  // POST /chat
- resetChat(sessionId)                         // POST /chat/reset
- getChatHistory(sessionId)                    // GET /chat/history
- listSessions()                               // GET /sessions
- triggerPdfFromChat(sessionId)                // POST /chat/pdf_trigger

// OCR
- extractText(file)                            // POST /extract

// Classification
- classifyCrime(text, entities)                // POST /classify

// RAG
- retrieveArticles(query, crimeType, topK)      // POST /retrieve

// Verification
- verifyEvidence(evidenceText, entities, classification, articles)  // POST /verify

// PDF Generation
- generatePdf(caseData)                        // POST /generate

// Health
- healthCheck()                                // GET /health
```

### API Hooks (`frontend/src/api/hooks.js`)
Custom React hooks for all API operations:

```javascript
- useAnalyze()          // Case analysis with progress tracking
- useChat(caseContext)  // Chatbot with session management
- usePdfDownload()      // PDF download functionality
- useCases()            // Case history management
- useHealthCheck()      // Service health monitoring
- useChatHistory()      // Chat history retrieval
- useSessions()         // Session listing
- useOcr()              // OCR text extraction
- useClassification()   // Crime classification
- useRag()              // Legal article retrieval
- useVerification()     // Evidence verification
- usePdfGeneration()    // PDF generation
```

## Frontend Pages & API Usage

### 1. LandingPage (`/`)
- Static landing page with feature showcase
- Links to analysis and dashboard

### 2. DashboardPage (`/dashboard`)
- Uses `useCases()` hook to fetch real case data
- Displays statistics (total, strong evidence, pending, avg score)
- Shows recent cases with status indicators
- Real-time data from `/cases` endpoint

### 3. CaseAnalysisPage (`/analyze`)
- Uses `useAnalyze()` hook for file upload and analysis
- Displays analysis progress
- Shows classification, entities, articles, verification results
- Generates PDF reports

### 4. ChatbotPage (`/chatbot`)
- Uses `useChat()` hook for chat functionality
- Session-based conversation with case context
- Arabic legal responses grounded in retrieved articles
- References Egyptian Law 175/2018

### 5. CaseHistoryPage (`/history`) - **NEW**
- Uses `useCases()` and `usePdfDownload()` hooks
- Lists all cases with search and filter
- Shows case status, crime type, score, grade
- View and download PDF reports
- Refresh functionality

### 6. SettingsPage (`/settings`)
- Uses `useHealthCheck()` hook
- Displays service health status (gateway + all microservices)
- Language configuration
- Privacy & security information
- API connection testing

## Routing (`frontend/src/App.jsx`)

```javascript
/           → LandingPage
/dashboard  → DashboardPage
/analyze    → CaseAnalysisPage
/history    → CaseHistoryPage  (NEW)
/chatbot    → ChatbotPage
/settings   → SettingsPage
```

## Sidebar Navigation (`frontend/src/components/layout/Sidebar.jsx`)

Updated navigation items:
- Home
- Dashboard
- New Case
- Case History (NEW)
- Legal Chat
- Settings

## Integration Features

### 1. Real-time Data
- All pages use live API data instead of mock data
- Automatic loading states and error handling
- Progress tracking for file uploads and analysis

### 2. Service Health Monitoring
- Settings page shows health of all microservices
- Visual indicators (healthy/unhealthy/unreachable)
- Real-time health check functionality

### 3. Case Management
- Complete case lifecycle: create → analyze → view → download
- Case history with search and filters
- Status tracking (processing/completed/failed)

### 4. Chatbot Integration
- Session-based conversations
- Case context awareness
- Arabic legal responses
- Article citation validation

### 5. PDF Generation
- On-demand PDF generation
- Download from case history
- Trigger from chatbot

## Error Handling

All hooks include:
- Loading states
- Error messages
- Try-catch blocks
- User-friendly error display

## Future Enhancements

Potential additions:
- WebSocket for real-time analysis updates
- Case sharing/collaboration
- Advanced filtering in case history
- Case comparison feature
- Export to other formats (DOCX, etc.)
- Multi-language support for all UI elements

## Environment Variables

Required:
- `VITE_API_URL` - Backend API base URL (default: http://localhost:8000)

## Notes

- All API calls go through the API Gateway (port 8000)
- The gateway orchestrates calls to microservices
- Case data is stored in-memory (replace with Redis/DB in production)
- Files are auto-deleted after 24 hours
- Rate limiting: 10 requests/minute per IP
