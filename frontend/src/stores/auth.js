import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase } from '../lib/supabase'

const EMAIL_KEY = 'last_email'

export const useAuth = defineStore('auth', () => {
  const user = ref(null)
  const isReady = ref(false)
  const lastEmail = ref('')

  // bootstrap user
  supabase.auth.getUser().then(({ data }) => {
    user.value = data?.user ?? null
    isReady.value = true
  })

  // listen for changes
  supabase.auth.onAuthStateChange((_event, session) => {
    user.value = session?.user ?? null
  })

    // load saved email (Electron secureStore if available, else localStorage)
    ; (async () => {
      if (window.secureStore?.getSession) {
        const saved = await window.secureStore.getSession(EMAIL_KEY)
        if (saved) lastEmail.value = saved
      } else {
        lastEmail.value = localStorage.getItem(EMAIL_KEY) || ''
      }
    })()

  const isLoggedIn = computed(() => !!user.value)

  const signInWithPassword = async (email, password, rememberEmail) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error

    // remember email toggle
    if (rememberEmail) {
      if (window.secureStore?.setSession) await window.secureStore.setSession(EMAIL_KEY, email)
      else localStorage.setItem(EMAIL_KEY, email)
      lastEmail.value = email
    } else {
      if (window.secureStore?.clearSession) await window.secureStore.clearSession(EMAIL_KEY)
      else localStorage.removeItem(EMAIL_KEY)
      lastEmail.value = ''
    }

    return { user: data?.user, session: data?.session }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  return { user, isReady, isLoggedIn, lastEmail, signInWithPassword, signOut }
})
