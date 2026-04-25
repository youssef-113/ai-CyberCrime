import { useState, useEffect } from 'react'
import { supabase } from '../../lib/supabase'
import { useSupabaseQuery, useSupabaseAuth } from '../../hooks/useSupabase'

/**
 * Example component showing Supabase integration
 * 
 * This demonstrates:
 * 1. Using the supabase client directly
 * 2. Using the useSupabaseQuery hook for data fetching
 * 3. Using the useSupabaseAuth hook for authentication
 */
export default function SupabaseExample() {
  // Example 1: Using the supabase client directly (low-level)
  const [todos, setTodos] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function getTodos() {
      const { data, error } = await supabase.from('todos').select()
      
      if (error) {
        console.error('Error fetching todos:', error)
      } else {
        setTodos(data || [])
      }
      setLoading(false)
    }

    getTodos()
  }, [])

  // Example 2: Using the useSupabaseQuery hook (recommended)
  const { 
    data: users, 
    loading: usersLoading, 
    error: usersError,
    refetch: refetchUsers 
  } = useSupabaseQuery('users', {
    select: 'id, email, full_name',
    order: { column: 'created_at', ascending: false },
    limit: 10,
  })

  // Example 3: Using the useSupabaseAuth hook
  const { user, session, signIn, signUp, signOut, loading: authLoading } = useSupabaseAuth()

  if (loading || usersLoading || authLoading) {
    return <div>Loading...</div>
  }

  return (
    <div className="p-6 space-y-8">
      {/* Direct Supabase Client Usage */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">Direct Client Usage</h2>
        <ul className="list-disc pl-5">
          {todos.map((todo) => (
            <li key={todo.id}>{todo.name}</li>
          ))}
        </ul>
      </section>

      {/* useSupabaseQuery Hook Usage */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">useSupabaseQuery Hook</h2>
        {usersError && <p className="text-red-500">Error: {usersError}</p>}
        <button 
          onClick={refetchUsers}
          className="px-4 py-2 bg-primary text-white rounded"
        >
          Refresh Users
        </button>
        <ul className="list-disc pl-5">
          {users.map((user) => (
            <li key={user.id}>{user.full_name || user.email}</li>
          ))}
        </ul>
      </section>

      {/* useSupabaseAuth Hook Usage */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">useSupabaseAuth Hook</h2>
        {user ? (
          <div className="space-y-2">
            <p>Logged in as: {user.email}</p>
            <button 
              onClick={signOut}
              className="px-4 py-2 bg-danger text-white rounded"
            >
              Sign Out
            </button>
          </div>
        ) : (
          <p>Not logged in</p>
        )}
      </section>
    </div>
  )
}
