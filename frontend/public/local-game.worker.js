/* All physics, AI and combat execute here, never on the remote service. */
let bootPromise;
let bootMessage = 'DOWNLOADING GAME ENGINE';
let py, runtime, command, socket, url, bootstrap;
let tickTimer, reportTimer, pingTimer, retryTimer, stopping = false;
let inFlight = false, latest, events = [], pendingReport, lastLocalProbe = 0;
let online = null, leaders = [], serviceRtt = null, syncError = false;
let finalNeeded = false;
const timestamp = () => performance.timeOrigin + performance.now();
const post = message => self.postMessage(message);

function publish() {
  if (!latest || inFlight) return;
  post({ ...latest, events }); latest = null; events = []; inFlight = true;
}

function sendReport() {
  if (!runtime) return;
  // Keep the same report until acknowledged, so retry is idempotent.
  if (!pendingReport) pendingReport = JSON.parse(runtime.report());
  post({ type: 'checkpoint', report: pendingReport });
  if (socket?.readyState === 1) socket.send(JSON.stringify(pendingReport));
}

function connectSocial() {
  if (stopping) return;
  socket = new WebSocket(url);
  socket.onopen = () => {
    syncError = false;
    socket.send(JSON.stringify({ type: 'ping', time: timestamp() }));
    if (pendingReport) socket.send(JSON.stringify(pendingReport));
    clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (socket.readyState === 1) socket.send(JSON.stringify({ type: 'ping', time: timestamp() }));
    }, 3000);
  };
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.type === 'social') {
      online = message.online; leaders = message.leaders;
      command(JSON.stringify({ type: 'settings', settings: message.settings }));
    } else if (message.type === 'pong') serviceRtt = Math.round(timestamp() - message.time);
    else if (message.type === 'saved') {
      command(JSON.stringify(message)); syncError = false;
      post({ type: 'saved', sequence: message.sequence });
      if (pendingReport?.sequence <= message.sequence) pendingReport = null;
      if (stopping && finalNeeded) { finalNeeded = false; sendReport(); }
      else if (stopping) socket.send(JSON.stringify({ type: 'leave' }));
    } else if (message.type === 'left') {
      socket.close(); post({ type: 'stopped' });
    } else if (message.type === 'sync_error') {
      if (!syncError) post({ type: 'action_error', message: message.message });
      syncError = true;
    }
  };
  socket.onclose = event => {
    clearInterval(pingTimer); online = null;
    if (!stopping && event.code !== 1008) retryTimer = setTimeout(connectSocial, 2000);
    else if (!stopping) { syncError = true; post({ type: 'action_error', message: 'Online session expired. Progress is kept for retry; leave and rejoin to reconnect.' }); }
  };
  socket.onerror = () => { syncError = true; };
}

function loading(message) {
  bootMessage = message;
  post({ type: 'loading', message });
}

async function asset(path, archive = false) {
  const response = await fetch(path, { signal: AbortSignal.timeout(30000) });
  if (!response.ok || response.headers.get('content-type')?.includes('text/html')) {
    throw new Error(`Missing game file: ${path.split('/').pop().split('?')[0]}. Please retry after the site is updated.`);
  }
  if (!archive) return response.json();
  const data = await response.arrayBuffer();
  const magic = new Uint8Array(data, 0, Math.min(2, data.byteLength));
  if (magic[0] !== 80 || magic[1] !== 75) throw new Error('Invalid game archive. Please retry after the site is updated.');
  return data;
}

function prepareEngine() {
  if (bootPromise) { loading(bootMessage); return bootPromise; }
  bootPromise = (async () => {
    const base = new URL('/local-runtime/', self.location.origin).href;
    loading('DOWNLOADING GAME ENGINE');
    const [stdlib, manifest] = await Promise.all([
      asset(base + 'python_stdlib.zip', true), asset(base + 'manifest.json'),
    ]);
    const archive = await asset(`${base}game.zip?v=${encodeURIComponent(manifest.version)}`, true);
    self.importScripts(base + 'pyodide.js');
    loading('STARTING GAME ENGINE');
    const stdlibURL = URL.createObjectURL(new Blob([stdlib]));
    try { py = await self.loadPyodide({ indexURL: base, stdLibURL: stdlibURL }); }
    finally { URL.revokeObjectURL(stdlibURL); }
    loading('LOADING PHYSICS');
    await py.loadPackage(['micropip', 'pydantic', 'cffi']);
    py.globals.set('asset_base', base);
    await py.runPythonAsync(`
import micropip
await micropip.install([
    asset_base + 'pymunk-7.2.0-cp313-cp313-pyodide_2025_0_wasm32.whl',
    asset_base + 'pathfinding-1.0.22-py3-none-any.whl'
], deps=False)
`);
    py.unpackArchive(archive, 'zip', { extractDir: '/game' });
    py.runPython("import sys; sys.path.insert(0, '/game'); import local_runtime");
    loading('GAME ENGINE READY');
  })();
  return bootPromise;
}

async function initialize(data) {
  bootstrap = data.bootstrap; url = data.url;
  await prepareEngine();
  if (stopping) return;
  loading('PREPARING WORLD');
  const init = py.globals.get('local_runtime').initialize;
  init(JSON.stringify(bootstrap)); init.destroy();
  runtime = py.globals.get('local_runtime').runtime;
  command = py.globals.get('local_runtime').command;
  let lastProgress = 0;
  while (!stopping) {
    const progress = JSON.parse(runtime.prepare_step());
    if (progress.ready) break;
    if (performance.now() - lastProgress > 250) {
      lastProgress = performance.now();
      post({ type: 'loading', message: `PREPARING WORLD ${progress.zombies} / ${progress.target}` });
    }
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  if (stopping) return;
  connectSocial();
  post({ type: 'open' });
  const tick = () => {
    if (stopping) return;
    const start = performance.now();
    try {
      const result = JSON.parse(runtime.tick());
      result.messages.forEach(post);
      latest = { ...result.state, online, leaders,
        network: { rtt: 0, jitter: 0, interval: 50, received_at: timestamp(),
                   service_rtt: serviceRtt, sync_online: socket?.readyState === 1 && !syncError } };
      events.push(...result.state.events);
      if (events.length > 256) events.splice(0, events.length - 256);
      publish();
      tickTimer = setTimeout(tick, Math.max(1, 50 - (performance.now() - start)));
    } catch (error) { post({ type: 'error', message: String(error) }); }
  };
  tick(); reportTimer = setInterval(sendReport, 4000);
}

self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'prewarm') await prepareEngine();
    else if (data.type === 'connect') await initialize(data);
    else if (data.type === 'state-consumed') { inFlight = false; publish(); }
    else if (data.type === 'disconnect') {
      stopping = true;
      finalNeeded = !!pendingReport;
      clearTimeout(tickTimer); clearInterval(reportTimer); clearTimeout(retryTimer);
      sendReport();
      setTimeout(() => { clearInterval(pingTimer); socket?.close(); post({ type: 'stopped' }); }, 2500);
    } else if (runtime) {
      if (data.type === 'input' && timestamp() - lastLocalProbe > 1000) {
        lastLocalProbe = timestamp(); post({ type: 'input-probe', sent_at: data.sent_at });
      }
      if (data.type === 'respawn') sendReport();
      command(JSON.stringify(data));
    }
  } catch (error) { post({ type: 'error', message: String(error) }); }
};