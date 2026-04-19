import client from './client'

export const analyzeEvidence = async (files, onProgress) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))

  const config = {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total))
      }
    },
  }

  const response = await client.post('/analyze', formData, config)
  return response.data
}

export const analyzeEvidenceJson = async (files, onProgress) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))

  const config = {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total))
      }
    },
  }

  const response = await client.post('/analyze/json', formData, config)
  return response.data
}

export const downloadPdf = async (caseId) => {
  const response = await client.get(`/pdf/${caseId}`, {
    responseType: 'blob',
  })
  return response.data
}

export const sendChatMessage = async (sessionId, message, caseContext) => {
  const response = await client.post('/chat', {
    session_id: sessionId,
    message,
    case_context: caseContext,
  })
  return response.data
}

export const getCaseHistory = async (params = {}) => {
  const response = await client.get('/cases', { params })
  return response.data
}

export const getCaseById = async (caseId) => {
  const response = await client.get(`/cases/${caseId}`)
  return response.data
}

export const healthCheck = async () => {
  const response = await client.get('/health')
  return response.data
}
