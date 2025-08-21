<!-- src/components/ClientDrawer.vue -->
<template>
    <transition name="slide">
        <aside v-if="visible" class="fixed top-0 right-0 bg-white shadow-xl overflow-auto h-screen w-1/2" role="dialog"
            aria-modal="true" aria-labelledby="drawer-title">
            <header class="flex items-center justify-between p-4 border-b">
                <h2 id="drawer-title" class="text-xl font-semibold">{{ title }}<span
                        class="bg-purple-100 text-purple-800 ml-2 text-xs font-medium me-2 px-2.5 py-0.5 rounded-sm dark:bg-purple-900 dark:text-purple-300">{{
                            details.company_id }}</span>
                </h2>
                <button @click="$emit('close')" aria-label="Close drawer" class="p-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                        stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </header>
            <section class="p-4">
                <!-- Let parent render content via slot -->
                <slot :details="details" :loading="loading" :error="error" :pdf-url="pdfUrl">
                    <!-- Fallback content if parent doesn't provide slot -->
                    <div v-if="loading" class="text-gray-500">Loading details…</div>
                    <div v-else-if="error" class="text-red-600">Error: {{ error }}</div>
                    <div v-else>
                        <p><strong>Total Time ({{ details.months }} mths):</strong> {{ details.total_time.toFixed(1) }}
                            hrs</p>
                        <p><strong>Average Usage:</strong> {{ details.average.toFixed(1) }} hrs/mo</p>
                        <p><strong>SLA:</strong> {{ details.sla }} hrs/mo</p>
                        <p><strong>Usage %:</strong> {{ details.percentage_usage ? details.percentage_usage.toFixed(1) +
                            '%' : 'N/A' }}</p>

                        <h3 class="mt-4 font-semibold">Monthly Breakdown</h3>
                        <ul class="list-disc list-inside">
                            <li v-for="(hrs, idx) in details.period_totals" :key="idx">
                                Month {{ idx + 1 }}: {{ hrs.toFixed(1) }} hrs
                            </li>
                        </ul>

                        <div v-if="details.current_period_logs?.length" class="mt-4">
                            <h3 class="font-semibold">Entries This Period</h3>
                            <ul class="list-decimal list-inside">
                                <li v-for="id in details.current_period_logs" :key="id">Entry #{{ id }}</li>
                            </ul>
                        </div>

                        <a :href="pdfUrl" target="_blank"
                            class="inline-block mt-6 px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700">Download
                            Detailed PDF</a>
                    </div>
                </slot>
            </section>
        </aside>
    </transition>
</template>

<script setup>
import { defineProps } from 'vue'

const props = defineProps({
    visible: Boolean,
    title: String,
    details: {
        type: Object,
        default: () => ({})
    },
    loading: Boolean,
    error: String,
    pdfUrl: String
})
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
    transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
    transform: translateX(100%);
}

.slide-enter-to,
.slide-leave-from {
    transform: translateX(0);
}
</style>