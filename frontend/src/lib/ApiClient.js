import axios from 'axios'
import { supabase } from './supabase'

export const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE,
})

api.interceptors.request.use(async (config) => {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})
