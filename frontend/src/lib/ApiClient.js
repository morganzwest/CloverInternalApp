import axios from 'axios'
import { supabase } from './supabase'

export const api = axios.create({
    baseURL: "https://cloverinternalapp.onrender.com",
})

api.interceptors.request.use(async (config) => {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})
