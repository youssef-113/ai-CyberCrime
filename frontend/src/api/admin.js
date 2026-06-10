import client from './client'

const ADMIN_BASE = '/admin'

export const adminApi = {
  // User Management
  listUsers: async (params = {}) => {
    const response = await client.get(`${ADMIN_BASE}/users`, { params })
    return response.data
  },

  getUser: async (userId) => {
    const response = await client.get(`${ADMIN_BASE}/users/${userId}`)
    return response.data
  },

  updateUser: async (userId, updateData) => {
    const response = await client.put(`${ADMIN_BASE}/users/${userId}`, updateData)
    return response.data
  },

  deleteUser: async (userId) => {
    const response = await client.delete(`${ADMIN_BASE}/users/${userId}`)
    return response.data
  },

  // Statistics
  getStats: async () => {
    const response = await client.get(`${ADMIN_BASE}/stats`)
    return response.data
  },

  // Case Management
  listCases: async (params = {}) => {
    const response = await client.get(`${ADMIN_BASE}/cases`, { params })
    return response.data
  },

  // Security Events
  listSecurityEvents: async (params = {}) => {
    const response = await client.get(`${ADMIN_BASE}/security-events`, { params })
    return response.data
  },

  resolveSecurityEvent: async (eventId) => {
    const response = await client.post(`${ADMIN_BASE}/security-events/${eventId}/resolve`)
    return response.data
  },
}
