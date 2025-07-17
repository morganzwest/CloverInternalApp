<template>
    <AppWrapper>
      <h1 class="text-2xl font-bold mb-4">Overhours Report</h1>
  
      <!-- Month/Year/Periods selectors with fetch button -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6 items-end">
        <!-- Filters Group -->
        <div class="grid grid-cols-1 sm:grid-cols-5 gap-4">
          <!-- Company Search -->
          <div class="sm:col-span-2">
            <label
              for="companySearch"
              class="block text-sm font-medium text-gray-700"
            >
              Company
            </label>
            <div class="mt-1 relative rounded-md text-sm">
              <input
                id="companySearch"
                type="text"
                v-model="searchQuery"
                placeholder="e.g. Acme Corp"
                class="block w-full pl-3 pr-10 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500"
                aria-label="Search companies"
              />
              <div
                class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none"
              >
                <!-- search icon -->
                <svg
                  class="h-5 w-5 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </div>
            </div>
          </div>
  
          <!-- Month Select -->
          <div>
            <label
              for="monthSelect"
              class="block text-sm font-medium text-gray-700"
            >
              Month
            </label>
            <select
              id="monthSelect"
              v-model="selectedMonth"
              class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option disabled value="">Select Month</option>
              <option v-for="m in months" :key="m.value" :value="m.value">
                {{ m.label }}
              </option>
            </select>
          </div>
  
          <!-- Year Select -->
          <div>
            <label
              for="yearSelect"
              class="block text-sm font-medium text-gray-700"
            >
              Year
            </label>
            <select
              id="yearSelect"
              v-model="selectedYear"
              class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option disabled value="">Select Year</option>
              <option v-for="y in years" :key="y" :value="y">
                {{ y }}
              </option>
            </select>
          </div>
  
          <!-- Number of Periods -->
          <div>
            <label
              for="numPeriods"
              class="block text-sm font-medium text-gray-700"
            >
              Months Avg.
            </label>
            <input
              id="numPeriods"
              type="number"
              v-model.number="selectedNumPeriods"
              min="1"
              max="12"
              placeholder="1–12"
              class="mt-1 block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500"
              aria-describedby="numPeriodsHelp"
            />
          </div>
        </div>
  
        <!-- Action & Toggle Group -->
        <div class="flex flex-col sm:flex-row sm:items-center gap-4">
          <!-- Load Report Button -->
          <button
            @click="fetchReport"
            :disabled="loading"
            class="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-emerald-600 border border-transparent rounded-md shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <span v-if="loading" class="flex items-center">
              <svg
                class="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                ></circle>
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8H4z"
                ></path>
              </svg>
              Loading…
            </span>
            <span v-else> Load Report </span>
          </button>
  
          <!-- Exempt Travel Toggle -->
          <label
            for="exemptTravel"
            class="inline-flex items-center cursor-pointer"
          >
            <input
              id="exemptTravel"
              v-model="exemptTravel"
              type="checkbox"
              class="sr-only peer"
              aria-checked="false"
            />
            <div
              class="w-11 h-6 bg-gray-200 rounded-full peer-focus:ring-4 peer-focus:ring-emerald-300 peer-checked:bg-emerald-600 relative after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border after:border-gray-300 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"
            ></div>
            <span class="ml-3 text-sm font-medium text-gray-900">
              Exempt Travel Time
            </span>
          </label>
        </div>
      </div>
  
      <!-- 1) Loading State -->
      <div
        v-if="loading"
        class="flex flex-col items-center justify-center py-16 space-y-2 text-gray-500"
      >
        <svg
          class="animate-spin h-8 w-8 text-emerald-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          />
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
        <p>Fetching companies over SLA…</p>
      </div>
  
      <!-- 2) Error State -->
      <div
        v-else-if="error"
        class="flex items-center justify-center py-16 text-red-600 font-medium"
      >
        <svg
          class="h-6 w-6 mr-2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M18.364 5.636l-12.728 12.728m0-12.728l12.728 12.728"
          />
        </svg>
        <span>Error loading data: {{ error }}</span>
      </div>
  
      <!-- 3) First‑run Empty State -->
      <div
        v-else-if="!hasFetched"
        class="flex flex-col items-center justify-center py-16 space-y-2 text-gray-500"
      >
        <svg
          class="h-12 w-12 text-gray-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"
          />
        </svg>
        <p>No data yet — click <strong>Load Report</strong> to get started.</p>
      </div>
  
      <!-- 4) No‑results Empty State -->
      <div
        v-else-if="!filteredCompanies.length"
        class="flex flex-col items-center justify-center py-16 space-y-2 text-gray-500"
      >
        <svg
          class="h-12 w-12 text-gray-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-4.35-4.35m2.1-5.15a8 8 0 11-16 0 8 8 0 0116 0z"
          />
        </svg>
        <p>
          No companies match your filters. Try adjusting your search or date
          range.
        </p>
      </div>
  
      <div v-else class="relative overflow-x-auto shadow-md sm:rounded-lg">
        <table
          v-if="filteredCompanies.length"
          class="w-full text-sm text-left text-gray-500"
        >
          <thead class="text-xs text-gray-700 uppercase bg-gray-200">
            <tr>
              <th class="px-6 py-3">Company Name</th>
              <th class="px-6 py-3 text-right">Monthly SLA</th>
              <th class="px-6 py-3 text-right">This Month Usage</th>
              <th class="px-6 py-3 text-right">Variation</th>
              <th class="px-6 py-3 text-right">Total SLA</th>
              <th class="px-6 py-3 text-right">Total Usage</th>
              <th class="px-6 py-3 text-right">Total Variation</th>
              <th class="px-6 py-3 text-right">Hourly Rate</th>
              <th class="px-6 py-3 text-right">Charge</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in filteredCompanies"
              :key="item.company_id"
              class="bg-white border-b border-gray-200 hover:bg-gray-100"
            >
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap"
              >
                <button
                  @click="openDrawer(item)"
                  class="hover:underline cursor-pointer hover:text-emerald-700"
                >
                  {{ item.name }}
                </button>
              </th>
              <td class="px-6 py-4 text-right">{{ item.sla.toFixed(1) }}hrs</td>
              <td class="px-6 py-4 text-right">
                {{ item.monthUsage.toFixed(1) }}hrs
              </td>
              <td class="px-6 py-4 text-right">
                <span
                  :class="item.monthVariation >= 0
                                  ? 'text-red-600 font-semibold'
                                  : 'text-green-600'
                                  "
                >
                  {{ item.monthVariation >= 0 ? '+' : ''
                  }}{{ item.monthVariation.toFixed(1) }}hrs
                </span>
              </td>
              <td class="px-6 py-4 text-right">
                {{ (item.sla * selectedNumPeriods).toFixed(1) }}hrs
              </td>
              <td class="px-6 py-4 text-right">
                {{ item.totalUsage.toFixed(1) }}hrs
              </td>
              <td class="px-6 py-4 text-right">
                <span
                  :class="item.totalVariation >= 0
                                  ? 'text-red-600 font-semibold'
                                  : 'text-green-600'
                                  "
                >
                  {{ item.totalVariation >= 0 ? '+' : ''
                  }}{{ item.totalVariation.toFixed(1) }}hrs
                </span>
              </td>
              <td class="px-6 py-4 text-right">
                {{ formatCurrency(item.hourlyRate) }}
              </td>
              <td class="px-6 py-4 text-right">
                <!-- NaN or infinite → error style -->
                <span
                  v-if="!Number.isFinite(item.charge)"
                  class="text-amber-600 font-semibold"
                >
                  Undefined
                </span>
  
                <!-- Positive charge → show currency -->
                <span v-else-if="item.charge > 0 && item.totalVariation > 0">
                  {{ formatCurrency(item.charge) }}
                </span>
  
                <!-- Negative or zero → blank -->
              </td>
            </tr>
          </tbody>
          <tfoot class="bg-gray-100">
            <tr>
              <td colspan="8" class="px-6 py-4 text-right font-semibold">
                Eligible Overcharges:
              </td>
              <td class="px-6 py-4 text-right font-semibold">
                {{ eligibleCount }}
              </td>
            </tr>
            <tr>
              <td colspan="8" class="px-6 py-4 text-right font-semibold">
                Total Overcharge:
              </td>
              <td class="px-6 py-4 text-right font-semibold">
                {{ formatCurrency(totalOvercharge) }}
              </td>
            </tr>
          </tfoot>
        </table>
        <ClientDrawer
          :visible="drawerVisible"
          :title="selectedCompany?.name"
          :details="details"
          :loading="loadingDetails"
          :error="detailsError"
          :pdf-url="pdfUrl"
          @close="closeDrawer"
        >
          <template #default="{ details, loading, error, pdfUrl }">
            <div v-if="loading" class="text-gray-500">Loading…</div>
            <div v-else-if="error" class="text-red-600">{{ error }}</div>
            <div
              v-else-if="details && details.total_time != null"
              class="space-y-6"
            >
              <!-- Overview -->
              <div class="bg-white rounded-lg">
                <h3 class="text-lg font-semibold mb-2">Overview</h3>
                <table class="w-full text-sm">
                  <tbody>
                    <tr>
                      <td class="py-1 font-medium">
                        Total Time ({{ details.months }} mths)
                      </td>
                      <td class="py-1 text-right">
                        {{ details.total_time.toFixed(1) }} hrs
                      </td>
                    </tr>
                    <tr class="bg-gray-50">
                      <td class="py-1 font-medium">Average Usage</td>
                      <td class="py-1 text-right">
                        {{ details.average.toFixed(1) }} hrs/mo
                      </td>
                    </tr>
                    <tr>
                      <td class="py-1 font-medium">SLA</td>
                      <td class="py-1 text-right">{{ details.sla }} hrs/mo</td>
                    </tr>
                    <tr class="bg-gray-50">
                      <td class="py-1 font-medium">Usage %</td>
                      <td class="py-1 text-right">
                        {{ details.percentage_usage.toFixed(1) }}%
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
  
              <!-- Monthly Breakdown -->
              <div class="bg-white rounded-lg">
                <h3 class="text-lg font-semibold mb-2">Monthly Breakdown</h3>
                <table class="w-full text-sm">
                  <thead>
                    <tr class="bg-gray-100">
                      <th class="py-1 px-2 text-left">Month</th>
                      <th class="py-1 px-2 text-right">Hours</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(hrs, idx) in details.period_totals || []"
                      :key="idx"
                      :class="idx % 2 === 0 ? '' : 'bg-gray-50'"
                    >
                      <td class="py-1 px-2">
                        {{ periodLabels[idx] || `Month ${idx + 1}` }}
                      </td>
                      <td class="py-1 px-2 text-right">
                        {{ hrs.toFixed(1) }} hrs
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
  
              <!-- Entries This Period -->
              <div v-if="loadingEntries" class="text-gray-500">
                Loading entries…
              </div>
              <div v-else-if="entriesError" class="text-red-600">
                {{ entriesError }}
              </div>
              <div v-else-if="entryDetails.length" class="bg-white rounded-lg">
                <h3 class="text-lg font-semibold mb-2">Entries This Period</h3>
  
                <!-- scroll wrapper: max height 16rem (64), adjust as needed -->
                <div class="max-h-64 overflow-y-auto">
                  <table class="w-full text-sm text-left">
                    <thead class="bg-gray-100 sticky top-0">
                      <tr>
                        <th class="px-2 py-1">Description</th>
                        <th class="px-2 py-1">Start</th>
                        <th class="px-2 py-1">End</th>
                        <th class="px-2 py-1 text-right">Hours</th>
                        <th class="px-2 py-1">Tag</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                      <tr
                        v-for="e in entryDetails"
                        :key="e.id"
                        class="even:bg-gray-50"
                      >
                        <td class="px-2 py-1 break-words">
                          {{ truncate(e.description, 30) }}
                        </td>
                        <td class="px-2 py-1">{{ formatShort(e.start_time) }}</td>
                        <td class="px-2 py-1">{{ formatShort(e.end_time) }}</td>
                        <td class="px-2 py-1 text-right">
                          {{ formatHoursToHhmm(e.hours) }}
                        </td>
                        <td class="px-2 py-1">{{ e.tag }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div v-else class="text-gray-500">No entries this period.</div>
  
              <!-- PDF Download -->
              <div class="text-right">
                <button
                  @click="downloadPdf"
                  :disabled="pdfLoading"
                  class="inline-flex items-center px-3 py-2 text-sm font-medium text-white rounded-md focus:ring-4 focus:ring-emerald-300"
                  :class="pdfLoading
                                      ? 'bg-gray-400 cursor-not-allowed'
                                      : 'bg-emerald-600 hover:bg-emerald-700'"
                >
                  <svg
                    v-if="pdfLoading"
                    class="animate-spin mr-2 h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      class="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      stroke-width="4"
                    ></circle>
                    <path
                      class="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8z"
                    ></path>
                  </svg>
                  <span v-if="!pdfLoading">Download Detailed PDF</span>
                  <span v-else>Generating...</span>
                </button>
              </div>
            </div>
            <div v-else class="text-gray-500">No details to show.</div>
          </template>
        </ClientDrawer>
      </div>
    </AppWrapper>
  </template>
  
  <script setup>
  import { ref, computed, watch } from 'vue'
  import AppWrapper from './AppWrapper.vue'
  import ClientDrawer from '../components/ClientDrawer.vue'
  import { api } from '../lib/ApiClient'
  import { saveAs } from 'file-saver'
  
  // Calculate default previous month
  const now = new Date()
  const prev = new Date(now)
  prev.setMonth(now.getMonth() - 1)
  const defaultMonth = String(prev.getMonth() + 1).padStart(2, '0')
  const defaultYear = String(prev.getFullYear())
  
  const companies = ref([])
  const loading = ref(false)
  const error = ref(null)
  const exemptTravel = ref(true)
  
const hasFetched = ref(false)
  function formatShort(dtString) {
      const d = new Date(dtString)
      const dd = String(d.getDate()).padStart(2, '0')
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const hh = String(d.getHours()).padStart(2, '0')
      const mi = String(d.getMinutes()).padStart(2, '0')
      return `${dd}/${mm}, ${hh}:${mi}`
  }
  function formatHoursToHhmm(decimalHours = 0) {
      const totalMinutes = Math.round(decimalHours * 60)
      const h = Math.floor(totalMinutes / 60)
      const m = totalMinutes % 60
      return `${h}:${String(m).padStart(2, '0')}`
  }
  
  const pdfLoading = ref(false)
  async function downloadPdf() {
      if (!selectedCompany.value) return
      pdfLoading.value = true
      const params = {
          period: `${selectedMonth.value}-${selectedYear.value}`,
          months: selectedNumPeriods.value,
          entry_type: 'Retained',
          ...(exemptTravel.value && { exclude_tag: 'Allowable travel time' })
      }
      try {
          const response = await api.get(
              `/reports/pdf/${selectedCompany.value.company_id}`,
              {
                  params,
                  responseType: 'blob'
              }
          )
          // option A: use file-saver
          saveAs(response.data, `company_${selectedCompany.value.company_id}_report.pdf`)
          pdfLoading.value = false
          // option B: manually create a download link:
          // const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
          // const link = document.createElement('a')
          // link.href = url
          // link.setAttribute('download', `company_${selectedCompany.value.company_id}_report.pdf`)
          // document.body.appendChild(link)
          // link.click()
          // document.body.removeChild(link)
          // window.URL.revokeObjectURL(url)
      } catch (err) {
          console.error('PDF download failed', err)
          // you can show a notification here
          pdfLoading.value = true
      }
  }
  
  // Selectors
  const months = Array.from({ length: 12 }, (_, i) => ({ label: String(i + 1).padStart(2, '0'), value: String(i + 1).padStart(2, '0') }))
  const years = Array.from({ length: 5 }, (_, i) => String(now.getFullYear() - i))
  const selectedMonth = ref(defaultMonth)
  const selectedYear = ref(defaultYear)
  const selectedNumPeriods = ref(6)
  const searchQuery = ref('')
  const details = ref({})
  const loadingDetails = ref(false)
  const detailsError = ref(null)
  const pdfUrl = ref('')
  
  const selectedCompany = ref(null)
  const drawerVisible = ref(false)
  
  
  function openDrawer(company) {
      selectedCompany.value = company
      drawerVisible.value = true
      fetchDetails(company)
  }
  
  function closeDrawer() {
      drawerVisible.value = false
      selectedCompany.value = null
  }
  
  const entryDetails = ref([])
  const loadingEntries = ref(false)
  const entriesError = ref(null)
  
  /**
   * Round a number to `n` decimal places.
   */
  function roundDecimals(num, n = 1) {
      return Number(num).toFixed(n)
  }
  
  /**
   * Truncate a string to `max` chars, adding “…” if it was longer.
   */
  function truncate(text = '', max = 30) {
      return text.length > max ? text.slice(0, max) + '…' : text
  }
  
  async function fetchEntryDetails(ids = []) {
      if (!ids.length) {
          entryDetails.value = []
          return
      }
  
      loadingEntries.value = true
      entriesError.value = null
      try {
          // uses ?ids=uuid1&ids=uuid2…
          const { data } = await api.get('/reports/time-entry-detail', {
              params: { ids }
          })
          entryDetails.value = data
      } catch (err) {
          entriesError.value = err.response?.data?.message || err.message
      } finally {
          loadingEntries.value = false
      }
  }
  
  watch(
      () => details.value.current_period_logs,
      (newIds) => {
          fetchEntryDetails(newIds || [])
      }
  )
  
  async function fetchDetails(company) {
      loadingDetails.value = true
      detailsError.value = null
      details.value = {}
      // clear old PDF if you use one
      pdfUrl.value = ''
  
      try {
          const params = {
              company_id: company.company_id,
              // period format “MM-YYYY” like your main report
              period: `${selectedMonth.value}-${selectedYear.value}`,
              months: selectedNumPeriods.value,
              include_logs: true,
              entry_type: 'Retained',
              // only include this param if your toggle is on
              ...(exemptTravel.value && { exclude_tag: 'Allowable travel time' })
          }
  
          const { data } = await api.get('/reports/company-usage', { params })
  
          // API should return { total_time, average, sla, percentage_usage,
          //          period_totals, current_period_logs, [pdf_url?] }
          details.value = data
          // if your payload includes a PDF link under a different key, adjust here:
          if (data.pdf_url) pdfUrl.value = data.pdf_url
      } catch (err) {
          detailsError.value = err.response?.data?.message || err.message
      } finally {
          loadingDetails.value = false
      }
  }
  
  // Compute footer metrics
  // 1) Who is eligible (over their SLA this month AND over on average)
  const eligible = computed(() =>
      sortedCompanies.value.filter(item =>
          item.monthVariation > 0 && item.totalVariation > 0
      )
  )
  
  const periodLabels = computed(() => {
      return (details.value.periods || []).map(([, endIso]) => {
          const d = new Date(endIso)
          return d.toLocaleString('en-GB', {
              month: 'long',
              year: 'numeric'
          })
      })
  })
  
  
  const filteredCompanies = computed(() => {
      return sortedCompanies.value.filter(item => item.monthVariation > 0)
          .filter(item => {
              const q = searchQuery.value.trim().toLowerCase()
              return !q || item.name.toLowerCase().includes(q)
          })
  })
  
  
  // 2) How many
  const eligibleCount = computed(() => eligible.value.length)
  
  // 3) Sum up their overcharges: hourlyRate * monthVariation
  const totalOvercharge = computed(() =>
      sortedCompanies.value.reduce((sum, item) => {
          if (Number.isFinite(item.charge) && item.charge > 0) {
              return sum + item.charge
          }
          return sum
      }, 0)
  )
  
  // Format currency
  const formatter = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' })
  function formatCurrency(value) {
      return formatter.format(value)
  }
  
  function sumUsage(arr) {
      return arr.reduce((sum, v) => sum + (v || 0), 0)
  }
  
  // Enriched & sorted data
  const sortedCompanies = computed(() => {
      return companies.value
          .map(c => {
              const monthUsage = c.period_usage.slice(-1)[0] || 0
              const totalUsage = c.period_usage.reduce((sum, v) => sum + (v || 0), 0)
              const monthVariation = monthUsage - c.sla
              const totalSla = c.sla * selectedNumPeriods.value
              const totalVariation = totalUsage - totalSla
              const hourlyRate = Number(c.company_raw.income_per_month) / c.sla
  
              // **New** charge calculation
              const charge = hourlyRate * monthVariation
  
              return {
                  company_id: c.company_id,
                  name: c.company_raw.name,
                  sla: c.sla,
                  monthUsage,
                  monthVariation,
                  totalUsage,
                  totalVariation,
                  hourlyRate,
                  charge
              }
          })
          .sort((a, b) => b.monthVariation - a.monthVariation)
  })
  
  async function fetchReport() {
      console.log(import.meta.env)
      if (!selectedMonth.value || !selectedYear.value) return
      loading.value = true
      error.value = null
      const period = `${selectedMonth.value}-${selectedYear.value}`
      try {
          const params = { period, num_periods: selectedNumPeriods.value, filter_monthly: true, entry_type: "Retained" }
          if (exemptTravel.value) params.exclude_tag = 'Allowable travel time'
          const { data } = await api.get('/reports/over-sla', { params })
          companies.value = data
      } catch (err) {
          error.value = err.response?.data?.message || err.message || 'Failed to load data'
      } finally {
          loading.value = false
          hasFetched.value = true
      }
  }
  </script>
  
  <style scoped>
  /* Optional: tune table styles */
  </style>
  