<template>
    <AppWrapper>
        <h1 class="text-2xl font-bold mb-6">Overhours Report</h1>
        <form @submit.prevent="downloadPdf" class="space-y-6">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

                <!-- Company ID Input -->
                <div>
                    <label for="companyId" class="block text-sm font-medium text-gray-700">Company ID</label>
                    <input id="companyId" type="text" v-model="companyId" placeholder="Enter company ID"
                        class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500" />

                    <!-- Loading / Name / Error -->
                    <div v-if="loadingCompany" class="mt-1 text-sm text-gray-500">
                        Loading company…
                    </div>
                    <div v-else-if="companyName" class="mt-1 text-sm text-gray-600">
                        Company: {{ companyName }}
                    </div>
                    <div v-else-if="companyId && companyError" class="mt-1 text-sm text-red-500">
                        Company not found.
                    </div>
                </div>

                <!-- Month Dropdown -->
                <div>
                    <label for="month" class="block text-sm font-medium text-gray-700">Month</label>
                    <select id="month" v-model="selectedMonth"
                        class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500">
                        <option disabled value="">Select Month</option>
                        <option v-for="m in months" :key="m.value" :value="m.value">
                            {{ m.label }}
                        </option>
                    </select>
                </div>

                <!-- Year Dropdown 2017–2026 -->
                <div>
                    <label for="year" class="block text-sm font-medium text-gray-700">Year</label>
                    <select id="year" v-model="selectedYear"
                        class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500">
                        <option disabled value="">Select Year</option>
                        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
                    </select>
                </div>

                <!-- Months Avg. Dropdown 1–12 -->
                <div>
                    <label for="periods" class="block text-sm font-medium text-gray-700">Months Avg.</label>
                    <select id="periods" v-model.number="selectedNumPeriods"
                        class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500">
                        <option disabled value="">Select</option>
                        <option v-for="n in 12" :key="n" :value="n">{{ n }}</option>
                    </select>
                </div>

                <!-- Exempt Travel -->
                <div class="flex items-center space-x-2">
                    <input id="exemptTravel" type="checkbox" v-model="exemptTravel"
                        class="h-4 w-4 text-emerald-600 border-gray-300 rounded" />
                    <label for="exemptTravel" class="text-sm font-medium text-gray-700">Exempt Travel Time</label>
                </div>
            </div>

            <!-- Submit Button -->
            <div>
                <button type="submit" :disabled="!companyId || !selectedMonth || !selectedYear || !selectedNumPeriods"
                    class="inline-flex items-center px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-md shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-50">
                    Download PDF
                </button>
            </div>
        </form>
    </AppWrapper>
</template>

<script setup>
import { ref, watch } from 'vue'
import debounce from 'lodash/debounce'
import AppWrapper from './AppWrapper.vue'
import { api } from '../lib/ApiClient'
import { saveAs } from 'file-saver'

// --- state ---
const companyId = ref('')
const companyName = ref('')
const companyError = ref(false)
const loadingCompany = ref(false)

const months = [
    { value: '01', label: 'January' },
    { value: '02', label: 'February' },
    { value: '03', label: 'March' },
    { value: '04', label: 'April' },
    { value: '05', label: 'May' },
    { value: '06', label: 'June' },
    { value: '07', label: 'July' },
    { value: '08', label: 'August' },
    { value: '09', label: 'September' },
    { value: '10', label: 'October' },
    { value: '11', label: 'November' },
    { value: '12', label: 'December' },
]
const years = Array.from({ length: 10 }, (_, i) => 2017 + i)  // 2017–2026
const selectedMonth = ref('')
const selectedYear = ref('2025')
const selectedNumPeriods = ref(6)
const exemptTravel = ref(true)

// --- fetch company whenever ID changes (debounced) ---
const fetchCompany = debounce(async (id) => {
    if (!id) {
        companyName.value = ''
        companyError.value = false
        return
    }
    loadingCompany.value = true
    companyError.value = false
    try {
        const resp = await api.get(`/companies/${id}`)
        companyName.value = resp.data.name || ''
    } catch {
        companyName.value = ''
        companyError.value = true
    } finally {
        loadingCompany.value = false
    }
}, 500)

watch(companyId, newId => {
    fetchCompany(newId.trim())
})

// --- PDF download ---
async function downloadPdf() {
    const id = companyId.value.trim()
    if (!id) return

    const params = {
        period: `${selectedMonth.value}-${selectedYear.value}`,
        months: selectedNumPeriods.value,
        ...(exemptTravel.value && { exclude_tag: 'Allowable travel time', entry_type: 'Retained' })
    }

    try {
        const resp = await api.get(`/reports/pdf/${id}`, {
            params,
            responseType: 'blob'
        })
        saveAs(resp.data, `company_${id}_report.pdf`)
    } catch (err) {
        console.error('PDF download failed', err)
    }
}
</script>

<style scoped>
/* your existing scoped styles */
</style>