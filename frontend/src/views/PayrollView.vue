<template>
  <AppWrapper>
    <div v-if="DEVMODE" class="flex items-center p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50" role="alert">
      <svg class="shrink-0 inline w-4 h-4 me-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 20 20">
        <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z"/>
      </svg>
      <span class="sr-only">Info</span>
      <div>
        <span class="font-medium">Upcoming Payroll Enhancements</span>
        <p class="mt-1">We're adding automatic calculations for overtime and gross payments, plus detailed breakdowns for every payroll period—coming soon.</p>
      </div>
    </div>
    <h1 class="text-2xl font-bold mb-4">Payroll Report</h1>

    <div class="grid grid-cols-1 sm:grid-cols-3 max-w-3xl gap-4 mb-6 items-end">
      <!-- Start Date -->
      <div>
        <label for="startDate" class="block text-sm font-medium text-gray-700">
          Start Date
        </label>
        <div class="mt-1 relative rounded-md shadow-sm">
          <input
            id="startDate"
            type="date"
            v-model="startDate"
            class="block w-full pl-3 pr-10 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500"
            aria-describedby="startDateHelp"
          />
          <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <!-- calendar icon (heroicons) -->
            <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M8 7V3m8 4V3m-9 8h10m-11 9h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
        </div>
        <p id="startDateHelp" class="mt-1 text-xs text-gray-500">
          Select the first day of the payroll period.
        </p>
      </div>
    
      <!-- End Date -->
      <div>
        <label for="endDate" class="block text-sm font-medium text-gray-700">
          End Date
        </label>
        <div class="mt-1 relative rounded-md shadow-sm">
          <input
            id="endDate"
            type="date"
            v-model="endDate"
            class="block w-full pl-3 pr-10 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500"
            aria-describedby="endDateHelp"
          />
          <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M8 7V3m8 4V3m-9 8h10m-11 9h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
        </div>
        <p id="endDateHelp" class="mt-1 text-xs text-gray-500">
          Select the last day of the payroll period.
        </p>
      </div>
    
      <!-- Action Button -->
      <div class="sm:mt-6">
        <button
          @click="fetchPayroll"
          :disabled="loading || !startDate || !endDate"
          class="w-full mb-5 inline-flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md shadow-sm
                 bg-emerald-600 text-white hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500
                 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          <span v-if="loading" class="flex items-center">
            <svg class="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none"
                 viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            Loading…
          </span>
          <span v-else>
            Load Payroll
          </span>
        </button>
      </div>
    </div>
    
    
    <div v-if="error" class="text-red-600 mb-4">{{ error }}</div>

    <div v-else class="overflow-x-auto shadow rounded-lg">
      <table class="w-full text-left">
        <thead class="bg-gray-200 uppercase text-xs text-gray-700">
          <tr>
            <th class="px-4 py-2">Name</th>
            <th class="px-4 py-2 text-right">Recorded</th>
            <th  class="px-4 py-2 text-right">Expenses</th>
            <th v-if="!DEVMODE" class="px-4 py-2 text-right">Standard Rate</th>
            <th v-if="!DEVMODE" class="px-4 py-2 text-right">Contracted Time</th>
            <th v-if="!DEVMODE" class="px-4 py-2 text-right">Overtime</th>
            <th v-if="!DEVMODE" class="px-4 py-2 text-right">Gross Amount</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-100">
          <tr v-for="row in sortedRows" :key="row.owner_id" class="hover:bg-gray-50">
            <td class="px-4 py-2">{{ row.name }}</td>
            <td class="px-4 py-2 text-right">
              {{ row.recorded.toFixed(2) }}h
              <small class="text-gray-500">({{ formatHoursToHhmm(row.recorded) }})</small>
            </td>
            <td class="px-4 py-2 text-right">{{ row.expenses.toFixed(2) }}h</td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">
              <span v-if="row.standardRate != null">
                {{ formatCurrency(row.standardRate) }}/h
              </span>
            </td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">{{ row.contractedTime.toFixed(2) }}h</td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">{{ row.overtime.toFixed(2) }}h</td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">
              <span v-if="row.grossAmount != null">{{ formatCurrency(row.grossAmount) }}</span>
            </td>
          </tr>
        </tbody>

        <tfoot v-if="sortedRows.length > 0" class="bg-gray-100 font-semibold">
          <tr>
            <td class="px-4 py-2">Total</td>
            <td class="px-4 py-2 text-right">{{ totalRecorded.toFixed(2) }}h</td>
            <td class="px-4 py-2"></td>
            <td v-if="!DEVMODE" class="px-4 py-2"></td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">{{ totalContractedTime.toFixed(2) }}h</td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">{{ totalOvertime.toFixed(2) }}h</td>
            <td v-if="!DEVMODE" class="px-4 py-2 text-right">{{ formatCurrency(totalGrossAmount) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </AppWrapper>
</template>

<script setup>
import { ref, computed } from 'vue'
import AppWrapper from './AppWrapper.vue'
import { api } from '../lib/ApiClient'

const DEVMODE = true

// Helpers
function calculateContractedHours(weeklyHours, startStr, endStr) {
  const start = new Date(startStr)
  const end = new Date(endStr)

  const isFullMonth =
    start.getDate() === 1 &&
    end.getDate() === new Date(end.getFullYear(), end.getMonth() + 1, 0).getDate()

  if (isFullMonth) {
    return (weeklyHours * 52) / 12
  } else {
    const msInWeek = 7 * 24 * 60 * 60 * 1000
    const weeks = Math.max(1, Math.floor((end - start) / msInWeek))
    return weeklyHours * weeks
  }
}

function formatHoursToHhmm(decimalHours = 0) {
  const totalMinutes = Math.round(decimalHours * 60)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  return `${h}:${String(m).padStart(2, '0')}`
}

const formatter = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  minimumFractionDigits: 2
})

function formatCurrency(v) {
  return formatter.format(v)
}

// Defaults
const now = new Date()
const defaultStart = new Date(now.getFullYear(), now.getMonth() - 2, 26)
const defaultEnd = new Date(now.getFullYear(), now.getMonth() - 1, 25)

function toIso(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const startDate = ref(toIso(defaultStart))
const endDate = ref(toIso(defaultEnd))
const loading = ref(false)
const error = ref(null)
const payroll = ref([])
const usersMap = ref({})
const ownersMap = ref({})

// fetch
async function fetchPayroll() {
  if (!startDate.value || !endDate.value) {
    error.value = 'Please select both dates.'
    return
  }
  loading.value = true
  error.value = null
  try {
    const { data } = await api.get('/reports/payroll/employees', {
      params: { start_date: startDate.value, end_date: endDate.value }
    })

    ownersMap.value = data.owners
    payroll.value = data.payroll.map(r => {
      const meta = ownersMap.value[r.owner_id] || {}
      const rate = meta.hourly_rate ?? null

      const contracted = calculateContractedHours(
        meta.contracted_hours ?? 0,
        startDate.value,
        endDate.value
      )

      const recorded = r.totalTime
      const overtime = meta.eligible_for_overtime
        ? Math.max(0, recorded - contracted)
        : 0

      const grossAmount = rate != null
        ? rate * (recorded < contracted ? contracted : recorded)
        : null

      return {
        owner_id: r.owner_id,
        name: '',
        recorded,
        expenses: r.expenses,
        standardRate: rate,
        contractedTime: contracted,
        overtime,
        grossAmount
      }
    })

    usersMap.value = data.users
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

// combine name and sort
const sortedRows = computed(() =>
  payroll.value
    .map(row => {
      const u = usersMap.value[row.owner_id] || {}
      return {
        ...row,
        name: u.firstName && u.lastName
          ? `${u.firstName} ${u.lastName}`
          : `#${row.owner_id}`
      }
    })
    .sort((a, b) => a.name.localeCompare(b.name))
)

const totalRecorded = computed(() =>
  payroll.value.reduce((sum, r) => sum + r.recorded, 0)
)

const totalOvertime = computed(() =>
  payroll.value.reduce((sum, r) => sum + r.overtime, 0)
)

const totalContractedTime = computed(() =>
  payroll.value.reduce((sum, r) => sum + r.contractedTime, 0)
)

const totalGrossAmount = computed(() =>
  payroll.value.reduce((sum, r) => sum + (r.grossAmount ?? 0), 0)
)
</script>

<style scoped>
.form-input {
  border: 1px solid #d1d5db;
  padding: 0.5rem;
  border-radius: 0.375rem;
}

tbody tr:hover {
  background-color: #f9fafb;
}
</style>
