import { createContext, useContext, useReducer, useCallback } from 'react'

const CaseContext = createContext(null)

const initialState = {
  currentCase: null,
  caseHistory: [],
  files: [],
  uploadProgress: 0,
  analysisResult: null,
  pipelineStep: 'idle',
  error: null,
}

const STEP_ORDER = ['idle', 'uploading', 'ocr', 'classifying', 'retrieving', 'verifying', 'scoring', 'generating', 'complete']

function caseReducer(state, action) {
  switch (action.type) {
    case 'SET_FILES':
      return { ...state, files: action.payload, error: null }
    case 'REMOVE_FILE':
      return { ...state, files: state.files.filter((f) => f.id !== action.payload) }
    case 'SET_UPLOAD_PROGRESS':
      return { ...state, uploadProgress: action.payload }
    case 'SET_PIPELINE_STEP':
      return { ...state, pipelineStep: action.payload }
    case 'SET_ANALYSIS_RESULT':
      return {
        ...state,
        analysisResult: action.payload,
        currentCase: action.payload?.case_id || state.currentCase,
        pipelineStep: 'complete',
      }
    case 'SET_CURRENT_CASE':
      return { ...state, currentCase: action.payload }
    case 'SET_CASE_HISTORY':
      return { ...state, caseHistory: action.payload }
    case 'SET_ERROR':
      return { ...state, error: action.payload, pipelineStep: 'idle' }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

export function CaseProvider({ children }) {
  const [state, dispatch] = useReducer(caseReducer, initialState)

  const setFiles = useCallback((files) => dispatch({ type: 'SET_FILES', payload: files }), [])
  const removeFile = useCallback((id) => dispatch({ type: 'REMOVE_FILE', payload: id }), [])
  const setUploadProgress = useCallback((p) => dispatch({ type: 'SET_UPLOAD_PROGRESS', payload: p }), [])
  const setPipelineStep = useCallback((step) => dispatch({ type: 'SET_PIPELINE_STEP', payload: step }), [])
  const setAnalysisResult = useCallback((result) => dispatch({ type: 'SET_ANALYSIS_RESULT', payload: result }), [])
  const setCurrentCase = useCallback((id) => dispatch({ type: 'SET_CURRENT_CASE', payload: id }), [])
  const setCaseHistory = useCallback((history) => dispatch({ type: 'SET_CASE_HISTORY', payload: history }), [])
  const setError = useCallback((error) => dispatch({ type: 'SET_ERROR', payload: error }), [])
  const resetCase = useCallback(() => dispatch({ type: 'RESET' }), [])

  const value = {
    ...state,
    stepIndex: STEP_ORDER.indexOf(state.pipelineStep),
    totalSteps: STEP_ORDER.length,
    stepOrder: STEP_ORDER,
    setFiles,
    removeFile,
    setUploadProgress,
    setPipelineStep,
    setAnalysisResult,
    setCurrentCase,
    setCaseHistory,
    setError,
    resetCase,
  }

  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>
}

export function useCase() {
  const context = useContext(CaseContext)
  if (!context) {
    throw new Error('useCase must be used within a CaseProvider')
  }
  return context
}

export default CaseContext
