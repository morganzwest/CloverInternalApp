<script setup>
import { ref } from 'vue'
import { useAuth } from '../stores/auth'

const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')
const auth = useAuth()

const submit = async () => {
    loading.value = true
    errorMsg.value = ''
    try {
        const { user, session } = await auth.signInWithPassword(email.value, password.value)
        console.log('User:', user)
        console.log('Session:', session)

        // Wait a tick for auth.user to populate
        if (user && session) {
            console.log('Authentication successful:', user, session)
            window.location.href = '/app'
        } else {
            console.error('Authentication failed: user or session is undefined')
            errorMsg.value = 'Authentication failed. Please try again.'
        }
    } catch (err) {
        console.error('Authentication error:', err)
        errorMsg.value = err.message || 'Authentication failed'
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <section class="bg-gray-50 ">
        <div class="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
            <a href="#" class="flex items-center mb-8 text-2xl font-semibold text-gray-900 ">
                <img class="h-10" src="https://i.ibb.co/xpF67pw/cloverlogo.png" alt="logo">
            </a>
            <div class="w-full bg-white rounded-lg shadow  md:mt-0 sm:max-w-md xl:p-0 ">
                <div class="p-6 space-y-4 md:space-y-6 sm:p-8">
                    <h1 class="text-xl font-bold leading-tight tracking-tight text-gray-900 md:text-2xl ">
                        Sign in to your account
                    </h1>
                    <form class="space-y-2 md:space-y-4" @submit.prevent="submit">
                        <div>
                            <label for="email" class="block mb-2 text-sm font-medium text-gray-900 ">Your
                                email</label>
                            <input v-model="email" type="email" name="email" id="email"
                                class="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-emerald-600 focus:border-emerald-600 block w-full p-2.5 "
                                placeholder="name@company.com" required="">
                        </div>
                        <div>
                            <label for="password" class="block mb-2 text-sm font-medium text-gray-900 ">Password</label>
                            <input v-model="password" type="password" name="password" id="password"
                                placeholder="••••••••"
                                class="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-emerald-600 focus:border-emerald-600 block w-full p-2.5 "
                                required="">
                        </div>
                        <div class="flex items-center justify-end">
                            <a href="#" class="text-sm font-medium text-emerald-600 hover:underline ">Forgot
                                password?</a>
                        </div>
                        <button type="submit"
                            class="cursor-pointer w-full text-white bg-emerald-600 hover:bg-emerald-700 focus:ring-4 focus:outline-none focus:ring-emerald-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center ">Sign
                            in</button>
                        <p class="text-sm font-light text-gray-500 ">
                            Don’t have an account yet? <a href="mailto:morgan.west@cloverhr.co.uk"
                                class="font-medium text-emerald-600 hover:underline ">Contact</a>
                        </p>
                    </form>
                </div>
            </div>
        </div>
    </section>
</template>
