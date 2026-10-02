// Edited real recordings; authors, sources and derivative licenses are in /audio/CREDITS.txt.
export const CREATURE_KINDS = ['normal', 'immolator', 'hellhound', 'hive', 'armored'];
const ACTIONS = ['idle', 'aggro', 'attack', 'hurt', 'death'];
const FILES = [...CREATURE_KINDS.flatMap(kind => ACTIONS.map(action => `${kind}-${action}`)), 'swarm'];
let loading;
const raw = {};
export function preloadCreatureSounds() {
  if (!loading) loading = Promise.all(FILES.map(async name => {
    const response = await fetch(`/audio/creatures/${name}.wav`);
    if (!response.ok) throw new Error('Failed to load creature sounds. You can reconnect.');
    raw[name] = await response.arrayBuffer();
  })).catch(error => { loading = null; throw error; });
  return loading;
}
export async function createCreatureSounds(ctx) {
  await preloadCreatureSounds();
  const decoded = await Promise.all(FILES.map(async name => [name, await ctx.decodeAudioData(raw[name].slice(0))]));
  return Object.fromEntries(decoded);
}