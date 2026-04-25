import client from './client'

const AUTH_BASE = '/auth'

export const authApi = {
  login: async (email, password) => {
    const response = await client.post(`${AUTH_BASE}/login`, { email, password })
    return response.data
  },

  register: async (email, password, full_name) => {
    const response = await client.post(`${AUTH_BASE}/register`, { email, password, full_name })
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
}
