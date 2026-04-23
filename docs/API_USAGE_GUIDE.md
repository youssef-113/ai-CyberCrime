# Frontend API Usage Guide

## Quick Start

### 1. Import the hook you need

```javascript
import { useAnalyze, useCases, useChat, usePdfDownload } from '../api/hooks'
```

### 2. Use the hook in your component

```javascript
function MyComponent() {
  const { analyze, loading, progress, error } = useAnalyze()
  
  const handleAnalyze = async (files) => {
    try {
      const result = await analyze(files)
      console.log('Analysis result:', result)
    } catch (err) {
      console.error('Analysis failed:', err)
    }
  }
  
  return <div>{/* your UI */}</div>
}
```

## Hook Reference

### useAnalyze()
Analyze evidence files with progress tracking.

```javascript
const { analyze, loading, progress, error } = useAnalyze()

// Usage
await analyze(files, jsonMode = true)
```

**Returns:**
- `analyze(files, jsonMode)` - Function to start analysis
- `loading` - Boolean, true while analyzing
- `progress` - Number (0-100), upload progress
- `error` - Error message string

**Example:**
```javascript
const files = [{ file: fileObject, name: 'screenshot.png' }]
const result = await analyze(files, true)
// result contains: case_id, classification, entities, articles, verification, score, timeline
```

---

### useChat(caseContext)
Chatbot with session management and case context.

```javascript
const { messages, sendMessage, loading, error, clearChat } = useChat(caseContext)

// Usage
await sendMessage('What is the penalty for blackmail?')
```

**Parameters:**
- `caseContext` - Object with case data (from analysis result)

**Returns:**
- `messages` - Array of message objects
- `sendMessage(content)` - Send a message
- `loading` - Boolean, true while bot is thinking
- `error` - Error message string
- `clearChat()` - Clear conversation history

**Example:**
```javascript
const caseContext = {
  case_id: 'CASE_ABC123',
  crime_type: 'blackmail',
  articles: [...],
  score: { total_score: 85, grade: 'STRONG' }
}

await sendMessage('What evidence do I need?')
// Response will be in Arabic and cite actual articles
```

---

### usePdfDownload()
Download PDF reports for completed cases.

```javascript
const { download, loading, error } = usePdfDownload()

// Usage
await download('CASE_ABC123')
```

**Returns:**
- `download(caseId)` - Download PDF for a case
- `loading` - Boolean, true while downloading
- `error` - Error message string

**Example:**
```javascript
await download('CASE_ABC123')
// PDF will download as: Cybercrime_AI_Report_CASE_ABC123.pdf
```

---

### useCases()
Manage case history and fetch individual cases.

```javascript
const { cases, fetchCases, fetchCase, loading, error } = useCases()

// Usage
await fetchCases()           // Get all cases
await fetchCase('CASE_ABC123') // Get specific case
```

**Returns:**
- `cases` - Array of case objects
- `fetchCases(params)` - Fetch all cases with optional filters
- `fetchCase(caseId)` - Fetch specific case by ID
- `loading` - Boolean, true while fetching
- `error` - Error message string

**Example:**
```javascript
// Get all cases
await fetchCases()
console.log(cases)

// Get specific case
const caseData = await fetchCase('CASE_ABC123')
console.log(caseData.classification, caseData.score)
```

---

### useHealthCheck()
Check health of all backend services.

```javascript
const { health, checkHealth, loading, error } = useHealthCheck()

// Usage
await checkHealth()
```

**Returns:**
- `health` - Object with service health status
- `checkHealth()` - Trigger health check
- `loading` - Boolean, true while checking
- `error` - Error message string

**Response Structure:**
```javascript
{
  gateway: "healthy",
  services: {
    ocr: "healthy",
    classifier: "healthy",
    rag: "healthy",
    verification: "healthy",
    pdf: "healthy"
  }
}
```

---

### useChatHistory()
Retrieve chat history for a session.

```javascript
const { history, fetchHistory, loading, error } = useChatHistory()

// Usage
await fetchHistory('session_12345')
```

**Returns:**
- `history` - Object with session history
- `fetchHistory(sessionId)` - Fetch history for session
- `loading` - Boolean, true while fetching
- `error` - Error message string

---

### useSessions()
List all active chat sessions.

```javascript
const { sessions, fetchSessions, loading, error } = useSessions()

// Usage
await fetchSessions()
```

**Returns:**
- `sessions` - Array of session objects
- `fetchSessions()` - Fetch all sessions
- `loading` - Boolean, true while fetching
- `error` - Error message string

---

### useOcr()
Extract text and entities from files.

```javascript
const { extract, loading, error } = useOcr()

// Usage
await extract(fileObject)
```

**Returns:**
- `extract(file)` - Extract text from file
- `loading` - Boolean, true while extracting
- `error` - Error message string

**Response Structure:**
```javascript
{
  text: "Extracted text...",
  entities: {
    phones: [{ type: "phone", value: "+201012345678", confidence: 0.95 }],
    amounts: [{ type: "amount", value: "5000 EGP", confidence: 0.90 }],
    dates: [{ type: "date", value: "15/11/2024", confidence: 0.85 }],
    accounts: [{ type: "account", value: "@username", confidence: 0.95 }],
    emails: []
  },
  confidence: 0.92,
  language: "ar"
}
```

---

### useClassification()
Classify crime type from evidence text.

```javascript
const { classify, loading, error } = useClassification()

// Usage
await classify(text, entities)
```

**Returns:**
- `classify(text, entities)` - Classify crime type
- `loading` - Boolean, true while classifying
- `error` - Error message string

**Response Structure:**
```javascript
{
  crime_type: "blackmail",
  confidence: 0.92,
  reasoning: "Evidence shows threats to expose private information...",
  suggested_articles: ["law175_art26", "law175_art25"],
  missing_evidence: ["Proof of financial loss", "Witness statements"]
}
```

---

### useRag()
Retrieve relevant law articles.

```javascript
const { retrieve, loading, error } = useRag()

// Usage
await retrieve(query, crimeType, topK = 5)
```

**Parameters:**
- `query` - Search query text
- `crimeType` - Type of crime (blackmail, scam, threat, etc.)
- `topK` - Number of results (default: 5)

**Returns:**
- `retrieve(query, crimeType, topK)` - Retrieve articles
- `loading` - Boolean, true while retrieving
- `error` - Error message string

**Response Structure:**
```javascript
{
  articles: [
    {
      article_number: "26",
      law: "175/2018",
      text: "Article text in Arabic...",
      relevance_score: 0.95,
      penalty_ar: "العقوبة المقررة..."
    }
  ]
}
```

---

### useVerification()
Verify evidence using multi-agent system.

```javascript
const { verify, loading, error } = useVerification()

// Usage
await verify(evidenceText, entities, classification, articles)
```

**Returns:**
- `verify(evidenceText, entities, classification, articles)` - Verify evidence
- `loading` - Boolean, true while verifying
- `error` - Error message string

**Response Structure:**
```javascript
{
  status: "APPROVED",
  rounds: 2,
  round_details: [
    {
      round: 1,
      attacker_challenge: "Is this evidence authentic?",
      judge_decision: "APPROVED - Evidence is verified",
      status: "APPROVED"
    }
  ],
  final_score: 85,
  score_breakdown: {
    grade: "STRONG",
    evidence_strength: 90,
    article_relevance: 85,
    entity_accuracy: 80
  },
  timeline: [...]
}
```

---

### usePdfGeneration()
Generate complaint PDF from case data.

```javascript
const { generate, loading, error } = usePdfGeneration()

// Usage
await generate(caseData)
```

**Parameters:**
- `caseData` - Object with case information

**Returns:**
- `generate(caseData)` - Generate PDF
- `loading` - Boolean, true while generating
- `error` - Error message string

**Example:**
```javascript
await generate({
  case_id: 'CASE_ABC123',
  crime_type: 'blackmail',
  evidence_summary: 'Summary of evidence...',
  timeline: [...],
  law_articles: [...],
  score: 85,
  grade: 'STRONG',
  complainant_name: 'John Doe',
  language: 'ar'
})
// PDF will download as: complaint_CASE_ABC123.pdf
```

---

## Complete Example: Full Analysis Flow

```javascript
import { useAnalyze, useCases, usePdfDownload } from '../api/hooks'

function AnalysisComponent() {
  const { analyze, loading: analyzing, progress, error: analyzeError } = useAnalyze()
  const { cases, fetchCases } = useCases()
  const { download } = usePdfDownload()

  const handleFullAnalysis = async (files) => {
    try {
      // Step 1: Analyze evidence
      const result = await analyze(files, true)
      console.log('Analysis complete:', result)
      
      // Step 2: Refresh case list
      await fetchCases()
      console.log('Cases updated:', cases)
      
      // Step 3: Download PDF (if completed)
      if (result.status === 'completed') {
        await download(result.case_id)
      }
    } catch (err) {
      console.error('Analysis failed:', err)
    }
  }

  return (
    <div>
      <input type="file" multiple onChange={(e) => handleFullAnalysis(e.target.files)} />
      {analyzing && <div>Progress: {progress}%</div>}
      {analyzeError && <div>Error: {analyzeError}</div>}
    </div>
  )
}
```

---

## Error Handling

All hooks throw errors that you should catch:

```javascript
try {
  const result = await analyze(files)
} catch (err) {
  // Error message is available in the error state
  console.error(error)
  // Or check err.response?.data?.detail for API error details
}
```

---

## Loading States

All hooks provide loading states:

```javascript
const { loading } = useAnalyze()

if (loading) {
  return <Spinner />
}
```

---

## TypeScript Support

For TypeScript users, all hooks are properly typed. Import types from the API module:

```typescript
import type { CaseData, ChatMessage, HealthStatus } from '../api/types'
```

---

## Best Practices

1. **Always handle errors**: Use try-catch blocks
2. **Show loading states**: Provide feedback to users
3. **Check data before use**: Verify data exists before rendering
4. **Use debouncing**: For search/filter operations
5. **Cache results**: Use React Query or similar for caching

---

## See Also

- [API Integration Summary](../API_INTEGRATION_SUMMARY.md) - Full API documentation
- [Backend API Docs](../services/api/main.py) - Backend endpoint details
