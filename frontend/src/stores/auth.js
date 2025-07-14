import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase } from '../lib/supabase'

export const useAuth = defineStore('auth', () => {
  const user = ref(null)
  const isReady = ref(false)

  // Load initial session
  supabase.auth.getUser().then(({ data }) => {
    user.value = data?.user ?? null
    isReady.value = true
  })

  // Listen for changes
  supabase.auth.onAuthStateChange((_event, session) => {
    user.value = session?.user ?? null
  })

  const isLoggedIn = computed(() => !!user.value)

  const signInWithPassword = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error

    const user = data?.user
    const session = {
      access_token: data?.session?.access_token,
      refresh_token: data?.session?.refresh_token,
      expires_at: data?.session?.expires_at
    }

    return { user, session }
  }



  const signOut = async () => {
    await supabase.auth.signOut()
  }

  return { user, isLoggedIn, signInWithPassword, signOut }
})
