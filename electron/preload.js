const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('secureStore', {
    getCreds: () => ipcRenderer.invoke('creds:get'),
    setCreds: (email, password) => ipcRenderer.invoke('creds:set', { email, password }),
    clearCreds: (email) => ipcRenderer.invoke('creds:clear', email),

    getSession: (key) => ipcRenderer.invoke('session:get', key),
    setSession: (key, json) => ipcRenderer.invoke('session:set', key, json),
    clearSession: (key) => ipcRenderer.invoke('session:clear', key),
});
