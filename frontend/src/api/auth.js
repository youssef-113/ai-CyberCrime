import client from './client'

const AUTH_BASE = '/auth'

export const authApi = {
  login: async (email, password) => {
    const response = await client.post(`${AUTH_BASE}/login`, { email, password })
    return response.data
  },

  register: async (email, password, full_name, phone = null) => {
    const response = await client.post(`${AUTH_BASE}/register`, {
      email,
      password,
      full_name,
      phone
    })
    return response.data
  },

  logout: async (token) => {
    const response = await client.post(`${AUTH_BASE}/logout`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.data
  },

  refresh: async (refreshToken) => {
    const response = await client.post(`${AUTH_BASE}/refresh`, { refresh_token: refreshToken })
    return response.data
  },

  verify: async () => {
    const response = await client.post(`${AUTH_BASE}/verify`)
    return response.data
  },

  getMe: async () => {
    const response = await client.get(`${AUTH_BASE}/me`)
    return response.data
  },

  changePassword: async (currentPassword, newPassword) => {
    const response = await client.put(`${AUTH_BASE}/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },

  getUsers: async () => {
    const response = await client.get(`${AUTH_BASE}/users`)
    return response.data
  },

  createSession: async (data = {}) => {
    const response = await client.post('/sessions', {
      ...data,
      linked_case_id: data.linked_case_id || null,
      model_used: data.model_used || null,
      temperature: data.temperature || 0.3,
      max_tokens: data.max_tokens || 800,
    })
    return response.data
  },

  listSessions: async (limit = 10, offset = 0) => {
    const response = await client.get(`/sessions/list`, {
      params: { limit, offset },
    })
    return response.data
  },

  getSession: async (sessionId) => {
    const response = await client.get(`/sessions/${sessionId}`)
    return response.data
  },

  getChatHistory: async (sessionId, limit = 50) => {
    const response = await client.get('/chat/history', {
      params: { session_id: sessionId, limit },
    })
    return response.data
  },
}
