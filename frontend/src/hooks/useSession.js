import { useState, useRef, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { audio } from '../game/audio';
import { checkpoint, acknowledge, recoverCheckpoints, flushOnExit } from '../game/localSync';

export const API = process.env.REACT_APP_BACKEND_URL + '/api';

const LOOT_LABELS = {
  gold: 'Gold', xp: 'XP', medkit: 'Medkit', faid: 'First Aid Kit',
  part: 'Weapon Part',
};
const TIER_LABELS = { 1: 'Common', 2: 'Uncommon', 3: 'Rare' };

export function useSession(engineRef) {
  const [mode, setMode] = useState('lobby'), [state, setState] = useState(null), [ping, setPing] = useState(null), [error, setError] = useState('');
  const [loadingMessage, setLoadingMessage] = useState('PREPARING WORLD');
  const workerRef = useRef(null), interval = useRef(null), connecting = useRef(false);
  const attemptRef = useRef(null), warmWorker = useRef(null);
  useEffect(() => {
    // Download and compile while the player chooses their character, not after Join.
    const worker = new Worker('/local-game.worker.js');
    warmWorker.current = worker;
    const discard = () => { if (warmWorker.current === worker) { worker.terminate(); warmWorker.current = null; } };
    worker.onmessage = ({ data }) => { if (data.type === 'error') discard(); };
    worker.onerror = discard;
    worker.postMessage({ type: 'prewarm' });
    return () => { warmWorker.current?.terminate(); warmWorker.current = null; };
  }, []);
  const teardown = useCallback(() => {
    const attempt = attemptRef.current;
    attemptRef.current = null;
    if (attempt) { clearTimeout(attempt.timeout); attempt.controller.abort(); }
    audio.stopAutomatic();
    audio.stopEnemies();
    clearInterval(interval.current); connecting.current = false;
    if (engineRef.current) engineRef.current.publishInput = null;
    if (workerRef.current) { const old = workerRef.current; old.postMessage({ type: 'disconnect' }); setTimeout(() => { old.terminate(); flushOnExit(); }, 3000); workerRef.current = null; }
  }, [engineRef]);
  const leave = useCallback(() => {
    teardown(); setMode('lobby'); setState(null); setPing(null); engineRef.current?.setMode('lobby', 'glock18');
  }, [teardown, engineRef]);
  useEffect(() => teardown, [teardown]);
  useEffect(() => { window.addEventListener('pagehide', flushOnExit); return () => window.removeEventListener('pagehide', flushOnExit); }, []);
  const start = async (name, weapon, skin = 'soldier') => {
    if (workerRef.current || connecting.current || !engineRef.current) return;
    connecting.current = true; setError(''); setState(null); setPing(null); setLoadingMessage('PREPARING WORLD'); setMode('connecting');
    const attempt = { controller: new AbortController(), timeout: null };
    attemptRef.current = attempt;
    const fail = message => {
      if (attemptRef.current !== attempt) return;
      teardown(); setError(message); setMode('lobby'); setState(null); setPing(null);
      engineRef.current?.setMode('lobby', weapon, skin);
    };
    const waitForState = () => {
      clearTimeout(attempt.timeout);
      attempt.timeout = setTimeout(() => fail('The game engine could not start. Please join again.'), connecting.current ? 120000 : 15000);
    };
    waitForState();
    try {
      // Audio permission/loading must never prevent the online handshake.
      audio.init(weapon).catch(() => {});
      await recoverCheckpoints();
      const storedToken = localStorage.getItem('dz_auth_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(storedToken ? { Authorization: `Bearer ${storedToken}` } : {}),
      };
      const response = await fetch(API+'/join', {
        method: 'POST',
        headers,
        credentials: 'include',
        signal: attempt.controller.signal,
        body: JSON.stringify({ name, weapon, skin })
      });
      const data = await response.json();
      if (attemptRef.current !== attempt) return;
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your call sign. Use 2–18 letters, numbers, spaces, periods, or hyphens.');
      const url = new URL(process.env.REACT_APP_BACKEND_URL); url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'; url.pathname = '/api/ws/'+data.token;
      const worker = warmWorker.current || new Worker('/local-game.worker.js');
      warmWorker.current = null; workerRef.current = worker;
      let inputSeq = 0, lastUI = 0, uiEvents = [];
      worker.onmessage = ({ data: message }) => {
        // Final checkpoints must survive a UI leave/unmount.
        if (message.type === 'checkpoint') { checkpoint(data.run_id, data.token, message.report); return; }
        if (message.type === 'saved') { acknowledge(data.run_id, message.sequence); return; }
        if (message.type === 'stopped') { worker.terminate(); return; }
        if (attemptRef.current !== attempt || workerRef.current !== worker) return;
        if (message.type === 'loading') { setLoadingMessage(message.message); waitForState(); return; }
        if (message.type === 'open') {
          // An open socket is not a playable game: wait for the first snapshot.
          const send = () => {
            if (workerRef.current !== worker) return;
            const input = engineRef.current?.getInput() || { type: 'input', x: 0, z: 0, fire: false };
            input.seq = ++inputSeq;
            input.sent_at = performance.timeOrigin + performance.now();
            engineRef.current?.movement.noteInput(input, performance.now());
            worker.postMessage(input);
          };
          engineRef.current.publishInput = send; send(); interval.current = setInterval(send, 50);
        } else if (message.type === 'input-probe') setPing(Math.max(0, Math.round(performance.timeOrigin + performance.now() - message.sent_at)));
        else if (message.type === 'action_error') toast.error(message.message, { id: 'action-error', duration: 3000 });
        else if (message.type === 'action_success') toast.success(message.message, { id: 'action-success', duration: 2500 });
        else if (message.type === 'state') {
          if (!message.me?.id || !Array.isArray(message.events)) {
            fail('The server returned incomplete game data. Please join again.'); return;
          }
          const firstState = connecting.current;
          if (firstState) {
            connecting.current = false;
            engineRef.current?.setMode('playing', weapon, skin); setMode('playing');
          }
          waitForState();
          engineRef.current?.receive(message);
          // HUD work stays at 10Hz; the renderer gets every available 20Hz state.
          uiEvents.push(...message.events); if (uiEvents.length > 256) uiEvents = uiEvents.slice(-256);
          if (firstState || performance.now() - lastUI >= 95) {
            setState({ ...message, events: uiEvents }); uiEvents = []; lastUI = performance.now();
          }
          audio.enemies(message);
          message.events.filter(e=>e.type==='boss_impact'||e.type==='boss_beam').slice(0,2).forEach(e=>audio.explosion(Math.hypot(e.x-message.me.x,e.z-message.me.z),e.x-message.me.x));
          message.events.forEach(e => {
            if (e.type === 'shot' && e.owner !== message.me.id) { const d=Math.hypot(e.x-message.me.x,e.z-message.me.z);audio.shot(e.weapon||'ak47',true,d,(e.x-message.me.x)/25); }
            if (e.type === 'explosion') audio.explosion(Math.hypot(e.x-message.me.x,e.z-message.me.z));
            if (e.type === 'supply' && e.owner === message.me.id) { audio.supply(); toast.success('Supplies acquired · Health and ammo restored', { id: 'supply', duration: 2500 }); }
            // Loot pickup notifications
            if (e.type === 'loot_pickup' && e.owner === message.me.id) {
              const label = e.kind === 'part'
                ? `${TIER_LABELS[e.tier] || ''} ${LOOT_LABELS.part}`
                : e.kind === 'equipment_part'
                  ? `+${e.amount || 1} ${e.part_id ? e.part_id.replace('_', ' ').toUpperCase() : 'Equipment Material'}`
                  : e.kind === 'calibration'
                    ? `+${e.amount || 1} Calibration Cartridge (T${e.tier || 1})`
                    : e.kind === 'gold'
                      ? `+${e.amount} ${LOOT_LABELS.gold}`
                      : LOOT_LABELS[e.kind] || e.kind;
              toast.success(label, { id: `loot-${e.kind}`, duration: 2000 });
            }
            // Calibration pity drop guaranteed
            if (e.type === 'calibration_guaranteed' && e.owner === message.me.id) {
              toast.success(`🎯 Pity Reward: ${e.calibration_id.replace('_', ' ').toUpperCase()} acquired!`, { id: 'pity-cal', duration: 3500 });
            }
            // Level up notification
            if (e.type === 'level_up' && e.owner === message.me.id) {
              toast.success(`Level Up! You are now Level ${e.level} · +${e.points} stat point${e.points > 1 ? 's' : ''}`, { id: 'levelup', duration: 4000 });
            }
            // Heal completion
            if (e.type === 'heal' && e.owner === message.me.id) {
              toast.success(`Healed +${e.amount} HP`, { id: 'heal', duration: 2000 });
            }
            // Craft success
            if (e.type === 'craft_success' && e.owner === message.me.id) {
              toast.success('Upgrade applied successfully!', { id: 'craft', duration: 2500 });
            }
            // Safe zone fire warning
            if (e.type === 'safe_zone_warning' && e.owner === message.me.id) {
              toast.warning(e.message || 'Combat disabled in Safe Zone!', { id: 'safe-zone-warning', duration: 1500 });
            }
          });
          worker.postMessage({ type: 'state-consumed' });
        } else if (message.type === 'close' || message.type === 'error') {
          fail(message.type === 'error' && message.message ? message.message.slice(0, 500) : message.code === 1013 ? 'The server is full. Try again shortly.' : 'The server connection was lost. You can join again.');
        }
      };
      worker.onerror = () => fail('Could not start the online connection. Please try again.');
      worker.postMessage({ type: 'connect', url: url.toString(), bootstrap: data });
    } catch (e) { fail(e.message || 'Could not join the game. Please try again.'); }
  };
  const respawn = () => workerRef.current?.postMessage({ type: 'respawn' });
  const equip = weapon => workerRef.current?.postMessage({ type: 'equip', weapon });
  const applyHeal = item => workerRef.current?.postMessage({ type: 'use_heal', item });
  const useConsumable = itemId => workerRef.current?.postMessage({ type: 'use_consumable', item_id: itemId, request_id: `${itemId}-${crypto.randomUUID()}` });
  const allocateStat = stat => workerRef.current?.postMessage({ type: 'allocate_stat', stat });
  const craft = (recipe, weapon) => workerRef.current?.postMessage({ type: 'craft', recipe, weapon });
  const equipmentCraft = itemId => workerRef.current?.postMessage({ type: 'equipment_craft', item_id: itemId });
  const equipmentUpgrade = itemId => workerRef.current?.postMessage({ type: 'equipment_upgrade', item_id: itemId });
  const equipmentEquip = (slot, itemId) => workerRef.current?.postMessage({ type: 'equipment_equip', slot, item_id: itemId });
  const convertMaterial = (sourceId, targetId) => workerRef.current?.postMessage({ type: 'material_convert', source_id: sourceId, target_id: targetId });
  const soldierBuy = tier => workerRef.current?.postMessage({ type: 'soldier_buy', tier });
  const soldierActivate = instanceId => workerRef.current?.postMessage({ type: 'soldier_activate', instance_id: instanceId });
  const soldierDeactivate = instanceId => workerRef.current?.postMessage({ type: 'soldier_deactivate', instance_id: instanceId });
  const soldierUpgrade = instanceId => workerRef.current?.postMessage({ type: 'soldier_upgrade', instance_id: instanceId });
  const soldierRename = (instanceId, nickname) => workerRef.current?.postMessage({ type: 'soldier_rename', instance_id: instanceId, nickname });
  const sellItem = (category, itemKey, amount = 1) => workerRef.current?.postMessage({ type: 'sell_item', category, item_key: itemKey, amount });
  const allianceCreate = name => workerRef.current?.postMessage({ type: 'alliance_create', name });
  const allianceJoin = code => workerRef.current?.postMessage({ type: 'alliance_join', code });
  const allianceLeave = () => workerRef.current?.postMessage({ type: 'alliance_leave' });
  const allianceFriendlyFire = enabled => workerRef.current?.postMessage({ type: 'alliance_friendly_fire', enabled });
  return {
    mode, state, ping, error, loadingMessage, start, leave, respawn, equip, applyHeal, onUseHeal: applyHeal, useHeal: applyHeal, useConsumable,
    allocateStat, craft, equipmentCraft, equipmentUpgrade, equipmentEquip, convertMaterial,
    soldierBuy, soldierActivate, soldierDeactivate, soldierUpgrade, soldierRename, sellItem,
    allianceCreate, allianceJoin, allianceLeave, allianceFriendlyFire
  };
}
