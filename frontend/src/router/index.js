import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import { supabase } from '../lib/supabase'

const routes = [
    {
        path: '/',
        component: LoginView,
        meta: { public: true },
    },
    {
        path: '/app',
        component: DashboardView,
        meta: { public: false },
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

router.beforeEach(async (to) => {
    const auth = useAuth()

    if (!auth.isReady) {
        const { data } = await supabase.auth.getUser()
        auth.user = data?.user ?? null
        auth.isReady = true
        console.log('Auth store initialized:', auth.user)
    }

    if (!to.meta.public && !auth.isLoggedIn) {
        console.log('User not logged in, redirecting to login')
        return { path: '/' }
    }
})

export default router
