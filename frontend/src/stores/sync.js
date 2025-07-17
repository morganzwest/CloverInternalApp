// src/stores/sync.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../lib/ApiClient'

export const useSyncStore = defineStore('sync', () => {
  // state
  const lastSync = ref(null)
  const error = ref(null)
  const loaded = ref(false)

  // action: fetch the last_sync timestamp via your axios client
  async function fetchLastSync() {
    error.value = null
    loaded.value = false
    try {
      const res = await api.get('/reports/last_sync')
      // assume the response shape is { last_sync: '2025-07-17T14:23:00Z' }
      lastSync.value = res.data.last_sync
    } catch (e) {
      // capture whatever error you get
      error.value = e
      console.error('useSyncStore.fetchLastSync error:', e)
    } finally {
      loaded.value = true
    }
  }

  // getter: nicely formatted
  const formattedSync = computed(() => {
    if (!lastSync.value) return ''
    const dt = new Date(lastSync.value)
    return dt.toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  })

  return {
    // state
    lastSync,
    error,
    loaded,
    // actions
    fetchLastSync,
    // getters
    formattedSync,
  }
})
