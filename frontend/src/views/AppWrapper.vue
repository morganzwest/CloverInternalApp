<template>
    <!-- Top navigation bar -->
    <header class="antialiased">
        <nav class="bg-white border-b border-gray-200 px-4 lg:px-6 py-3 ">
            <div class="flex justify-between items-center mx-auto max-w-7xl">
                <!-- Logo / Brand -->
                <RouterLink to="/" class="flex items-center gap-2 group">
                    <img src="https://www.cloverhr.co.uk/wp-content/uploads/2023/03/logo-1.png" alt="AcmePro logo"
                        class="h-8 w-auto" />
                </RouterLink>

                <!-- emerald navigation links (desktop) -->
                <ul class="flex gap-6">
                    <li>
                        <RouterLink to="/app" class="text-gray-700 hover:text-emerald-700  font-medium"
                            active-class="text-emerald-700 ">Overhours</RouterLink>
                    </li>
                    <li>
                        <RouterLink to="/app" class="text-gray-700 hover:text-emerald-700  font-medium"
                            active-class="text-emerald-700 ">Consultancy</RouterLink>
                    </li>
                    <li>
                        <RouterLink to="/app/report" class="text-gray-700 hover:text-emerald-700  font-medium"
                            active-class="text-emerald-700 ">Client Report</RouterLink>
                    </li>
                    <li>
                        <RouterLink to="/app/payroll" class="text-gray-700 hover:text-emerald-700  font-medium"
                            active-class="text-emerald-700 ">Payroll</RouterLink>
                    </li>
                </ul>

                <!-- Right-hand actions -->
                <div class="flex items-center gap-2">
                    <!-- Mobile menu toggle -->
                    <button @click="toggleMobileNav"
                        class="md:hidden p-2 rounded-lg hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200 "
                        aria-label="Toggle navigation">
                        <svg class="w-6 h-6 text-gray-600 " fill="none" stroke="currentColor" stroke-width="2"
                            viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M4 6h16M4 12h16M4 18h16" />
                        </svg>
                    </button>

                    <!-- Logout button -->
                    <button @click="handleLogout"
                        class="inline-flex cursor-pointer items-center bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-3 py-1.5 rounded-lg focus:ring-4 focus:ring-emerald-300 ">
                        <svg class="mr-1 w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd"
                                d="M3 4.5A1.5 1.5 0 0 1 4.5 3h6A1.5 1.5 0 0 1 12 4.5v3a.5.5 0 0 1-1 0v-3a.5.5 0 0 0-.5-.5h-6a.5.5 0 0 0-.5.5v11a.5.5 0 0 0 .5.5h6a.5.5 0 0 0 .5-.5v-3a.5.5 0 0 1 1 0v3A1.5 1.5 0 0 1 10.5 17h-6A1.5 1.5 0 0 1 3 15.5v-11ZM14.354 11.354a.5.5 0 0 0 0-.708l-2-2a.5.5 0 0 0-.708.708L13.293 10H7.5a.5.5 0 0 0 0 1h5.793l-1.647 1.646a.5.5 0 0 0 .708.708l2-2Z"
                                clip-rule="evenodd" />
                        </svg>
                        Logout
                    </button>
                </div>
            </div>
        </nav>
    </header>

    <!-- Main content area -->
    <main class="my-8 rounded-xl shadow border border-gray-200 p-8 bg-white mx-auto max-w-5/6">
        <slot />
    </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const mobileNavOpen = ref(false)
const router = useRouter()
const auth = useAuth()

function toggleMobileNav() {
    mobileNavOpen.value = !mobileNavOpen.value
}

async function handleLogout() {
    try {
        await auth.signOut()
        router.push('/') // Redirect to login or homepage
    } catch (err) {
        console.error('Logout failed:', err)
    }
}
</script>


<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>
