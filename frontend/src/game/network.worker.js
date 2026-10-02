/* Socket timing stays off the render thread. At most one state waits on the UI. */
let socket, pulse, heartbeat, latest, inFlight = false, events = [];
let controls = { type: 'input', x: 0, z: 0, angle: 0, fire: false };
let lastInput = 0, lastSent = 0, lastState = 0, interval = 50, rtt = null, jitter = 0;
let pendingPress = false;
const pings = new Map();
const stop = () => { clearInterval(pulse); clearInterval(heartbeat); pings.clear(); };
const timestamp = () => performance.timeOrigin + performance.now();

function sendInput() {
  if (socket?.readyState !== 1 || socket.bufferedAmount > 8192) return;
  socket.send(JSON.stringify({ ...controls, fire_pressed: pendingPress }));
  controls.reload = false; pendingPress = false; lastSent = performance.now();
}
function publish() {
  if (!latest || inFlight) return;
  self.postMessage({ ...latest, events });
  latest = null; events = []; inFlight = true;
}
function ping() {
  if (socket?.readyState !== 1 || socket.bufferedAmount > 8192) return;
  const now = performance.now();
  for (const [key, value] of pings) if (now - value > 10000) pings.delete(key);
  pings.set(now, now);
  socket.send(JSON.stringify({ type: 'ping', time: now }));
}

self.onmessage = ({ data }) => {
  if (data.type === 'connect') {
    stop(); latest = null; events = []; inFlight = false;
    socket = new WebSocket(data.url);
    socket.onopen = () => {
      self.postMessage({ type: 'open' });
      pulse = setInterval(() => {
        if (performance.now() - lastInput > 400) {
          controls = { ...controls, x: 0, z: 0, fire: false, reload: false, sprint: false };
          pendingPress = false;
        }
        if (performance.now() - lastSent >= 45) sendInput();
      }, 25);
      ping(); heartbeat = setInterval(ping, 1000);
    };
    socket.onmessage = e => {
      let m;
      try { m = JSON.parse(e.data); } catch { return; }
      const now = performance.now();
      if (m.type === 'state') {
        if (lastState) interval += (Math.min(1000, now - lastState) - interval) * .15;
        lastState = now;
        latest = { ...m, network: { rtt, jitter, interval, received_at: timestamp() } };
        events.push(...(m.events || []));
        if (events.length > 256) events.splice(0, events.length - 256);
        publish();
      } else if (m.type === 'pong' && pings.has(m.time)) {
        const value = now - pings.get(m.time); pings.delete(m.time);
        if (rtt !== null) jitter += (Math.abs(value - rtt) - jitter) * .25;
        rtt = value;
        self.postMessage({ type: 'ping', value: Math.round(value), jitter: Math.round(jitter) });
      } else if (m.type !== 'pong') self.postMessage(m);
    };
    socket.onclose = event => { stop(); self.postMessage({ type: 'close', code: event?.code }); };
    socket.onerror = () => self.postMessage({ type: 'error' });
  } else if (data.type === 'state-consumed') {
    inFlight = false; publish();
  } else if (data.type === 'input') {
    const edge = ['x', 'z', 'fire', 'sprint'].some(key => data[key] !== controls[key]) || data.reload;
    pendingPress ||= !!data.fire && !controls.fire;
    controls = { ...data, reload: !!data.reload || controls.reload };
    lastInput = performance.now();
    if (edge || lastInput - lastSent >= 50) sendInput();
  } else if (data.type === 'equip') {
    pendingPress = false; controls = { ...controls, fire: false, reload: false };
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'equip', weapon: data.weapon }));
  } else if (data.type === 'respawn') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'respawn' }));
  } else if (data.type === 'use_heal') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'use_heal', item: data.item }));
  } else if (data.type === 'use_consumable') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'use_consumable', item_id: data.item_id, request_id: data.request_id }));
  } else if (data.type === 'allocate_stat') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'allocate_stat', stat: data.stat }));
  } else if (data.type === 'craft') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'craft', recipe: data.recipe, weapon: data.weapon }));
  } else if (data.type === 'alliance_create' || data.type === 'alliance_leave') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: data.type, name: data.name }));
  } else if (data.type === 'alliance_join') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'alliance_join', code: data.code }));
  } else if (data.type === 'alliance_friendly_fire') {
    if (socket?.readyState === 1) socket.send(JSON.stringify({ type: 'alliance_friendly_fire', enabled: data.enabled }));
  } else if (['equipment_craft', 'equipment_upgrade', 'equipment_equip', 'material_convert', 'soldier_buy', 'soldier_activate', 'soldier_deactivate', 'soldier_upgrade', 'soldier_rename', 'sell_item'].includes(data.type)) {
    if (socket?.readyState === 1) socket.send(JSON.stringify(data));
  } else if (data.type === 'disconnect') {
    stop(); socket?.close(); latest = null; events = [];
  }
};
