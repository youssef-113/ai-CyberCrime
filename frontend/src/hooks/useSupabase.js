import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabase'

/**
 * Hook to fetch data from a Supabase table
 * @param {string} table - Table name
 * @param {object} options - Query options (select, filters, order, limit)
 */
export function useSupabaseQuery(table, options = {}) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const { select = '*', filters = [], order = null, limit = null } = options

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      let query = supabase.from(table).select(select)

      // Apply filters
      filters.forEach(({ column, operator, value }) => {
        query = query.filter(column, operator, value)
      })

      // Apply ordering
      if (order) {
        query = query.order(order.column, { ascending: order.ascending })
      }

      // Apply limit
      if (limit) {
        query = query.limit(limit)
      }

      const { data: result, error: supabaseError } = await query

      if (supabaseError) throw supabaseError

      setData(result || [])
    } catch (err) {
      setError(err.message)
      console.error('Supabase query error:', err)
    } finally {
      setLoading(false)
    }
  }, [table, select, filters, order, limit])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

/**
 * Hook to subscribe to real-time changes in a Supabase table
 * @param {string} table - Table name
 * @param {string} event - Event type (INSERT, UPDATE, DELETE, *)
 * @param {function} callback - Callback function when event occurs
 */
export function useSupabaseSubscription(table, event = '*', callback) {
  useEffect(() => {
    const subscription = supabase
      .channel(`${table}-changes`)
      .on('postgres_changes', { event, schema: 'public', table }, callback)
      .subscribe()

    return () => {
      subscription.unsubscribe()
    }
  }, [table, event, callback])
}

/**
 * Hook for Supabase auth state
 */
export function useSupabaseAuth() {
  const [user, setUser] = useState(null)
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = useCallback(async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    return data
  }, [])

  const signUp = useCallback(async (email, password, metadata = {}) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: metadata },
    })
    if (error) throw error
    return data
  }, [])

  const signOut = useCallback(async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }, [])

  return { user, session, loading, signIn, signUp, signOut }
}

/**
 * Insert data into a Supabase table
 */
export async function insertData(table, data) {
  const { data: result, error } = await supabase.from(table).insert(data).select()
  if (error) throw error
  return result
}

/**
 * Update data in a Supabase table
 */
export async function updateData(table, id, data) {
  const { data: result, error } = await supabase.from(table).update(data).eq('id', id).select()
  if (error) throw error
  return result
}

/**
 * Delete data from a Supabase table
 */
export async function deleteData(table, id) {
  const { error } = await supabase.from(table).delete().eq('id', id)
  if (error) throw error
}
