// electron/main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const keytar = require('keytar');

const isDev = !app.isPackaged;
const SERVICE = 'CloverInternal';

let PDF_PORT = 0;
let win, apiProc, API_PORT;

/* ---------- Secure storage IPC (keytar) ---------- */
ipcMain.handle('creds:get', async () => {
    const accounts = await keytar.findCredentials(SERVICE);
    return accounts[0] || null; // {account, password}
});
ipcMain.handle('creds:set', async (_e, { email, password }) => {
    await keytar.setPassword(SERVICE, email, password);
    return true;
});
ipcMain.handle('creds:clear', async (_e, email) => {
    if (email) return keytar.deletePassword(SERVICE, email);
    const accounts = await keytar.findCredentials(SERVICE);
    await Promise.all(accounts.map(a => keytar.deletePassword(SERVICE, a.account)));
    return true;
});

ipcMain.handle('session:get', async (_e, key = 'supabase') => {
    const v = await keytar.getPassword(SERVICE, key);
    return v || null;
});
ipcMain.handle('session:set', async (_e, key, json) => {
    await keytar.setPassword(SERVICE, key, json);
    return true;
});
ipcMain.handle('session:clear', async (_e, key = 'supabase') => {
    await keytar.deletePassword(SERVICE, key);
    return true;
});

/* ---------- API base for renderer ---------- */
ipcMain.on('api-base-sync', (e) => {
    e.returnValue = `http://127.0.0.1:${API_PORT}`;
});

/* ---------- Helpers ---------- */
function waitFor(url, timeoutMs = 15000, intervalMs = 200) {
    const deadline = Date.now() + timeoutMs;
    return new Promise((resolve, reject) => {
        (function tick() {
            const req = http.get(url, res => {
                res.resume();
                if (res.statusCode && res.statusCode < 500) resolve();
                else Date.now() > deadline ? reject(new Error('health timeout')) : setTimeout(tick, intervalMs);
            });
            req.on('error', () => Date.now() > deadline ? reject(new Error('health timeout')) : setTimeout(tick, intervalMs));
        })();
    });
}

/* ---------- Start backend (dynamic port) ---------- */
function startPdfServer() {
    return new Promise((resolve) => {
        const srv = http.createServer(async (req, res) => {
            if (req.method === 'POST' && req.url === '/pdf') {
                let body = '';
                req.on('data', c => body += c);
                req.on('end', async () => {
                    let w;
                    try {
                        const { html, url, options, base } = JSON.parse(body || '{}');
                        if (!html && !url) { res.writeHead(400); return res.end('missing html or url'); }

                        w = new BrowserWindow({ show: false, webPreferences: { sandbox: true } });

                        if (html) {
                            const data = 'data:text/html;base64,' + Buffer.from(html).toString('base64');
                            await w.loadURL(data, { baseURLForDataURL: base || 'about:blank' });
                        } else {
                            await w.loadURL(url);
                        }

                        // wait for fonts if present
                        await w.webContents.executeJavaScript('document.fonts && document.fonts.ready');

                        const pdf = await w.webContents.printToPDF({
                            printBackground: true,
                            preferCSSPageSize: true,
                            marginsType: 0,
                            pageSize: 'A4',
                            landscape: !!(options && options.landscape)
                        });

                        res.writeHead(200, { 'Content-Type': 'application/pdf' });
                        res.end(pdf);
                    } catch (e) {
                        res.writeHead(500); res.end(String(e));
                    } finally {
                        if (w) w.destroy();
                    }
                });
            } else if (req.method === 'GET' && req.url === '/health') {
                res.writeHead(200); res.end('ok');
            } else {
                res.writeHead(404); res.end();
            }
        });
        srv.listen(0, '127.0.0.1', () => { PDF_PORT = srv.address().port; resolve(); });
    });
}

async function startApi() {
    const { default: getPort, makeRange } = await import('get-port'); // ESM
    try {
        API_PORT = await getPort({ port: makeRange(8000, 8100) });
    } catch {
        API_PORT = 8000;
    }

    const exePath = isDev
        ? path.join(__dirname, '../backend/dist/api.exe')
        : path.join(process.resourcesPath, 'api', 'api.exe');

    apiProc = spawn(exePath, [], {
        env: {
            ...process.env,
            PACKAGED: isDev ? '0' : '1',
            API_PORT: String(API_PORT),
            ELECTRON_PDF_URL: `http://127.0.0.1:${PDF_PORT}/pdf`
        },
        windowsHide: true
    });

    apiProc.stdout.on('data', d => console.log('[api]', d.toString()));
    apiProc.stderr.on('data', d => console.error('[api]', d.toString()));
    apiProc.on('exit', () => app.quit());

    await waitFor(`http://127.0.0.1:${API_PORT}/health`).catch(() => { });
}

/* ---------- Create window ---------- */
async function createWindow() {
    await startPdfServer();
    await startApi();

    win = new BrowserWindow({
        width: 1280,
        height: 800,
        title: 'Clover Internal',
        webPreferences: {
            sandbox: true,
            contextIsolation: true,
            nodeIntegration: false,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    if (isDev) {
        const devUrl = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173';
        await win.loadURL(devUrl);
        win.webContents.openDevTools({ mode: 'detach' });
    } else {
        await win.loadFile(path.join(__dirname, '../frontend/dist/index.html'));
    }
}

/* ---------- App lifecycle ---------- */
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
    app.quit();
} else {
    app.on('second-instance', () => { if (win) { win.show(); win.focus(); } });
    app.whenReady().then(createWindow).catch(err => { console.error('startup fail:', err); app.quit(); });
    app.on('window-all-closed', () => { if (apiProc) apiProc.kill(); app.quit(); });
    app.on('quit', () => { if (apiProc) { try { apiProc.kill(); } catch { } } });
}
