import { createClient } from '@supabase/supabase-js';

const storageKey = 'supabase';
const hasSecure = typeof window !== 'undefined' && window.secureStore && window.secureStore.getSession;

const secureStorage = {
  async getItem() { return hasSecure ? await window.secureStore.getSession(storageKey) : localStorage.getItem(storageKey); },
  async setItem(_, v) { return hasSecure ? await window.secureStore.setSession(storageKey, v) : localStorage.setItem(storageKey, v); },
  async removeItem() { return hasSecure ? await window.secureStore.clearSession(storageKey) : localStorage.removeItem(storageKey); }
};

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
  {
    auth: {
      flowType: 'pkce',
      autoRefreshToken: true,
      persistSession: true,
      storage: secureStorage,
      storageKey
    }
  }
);
