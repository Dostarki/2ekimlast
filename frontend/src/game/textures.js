import * as THREE from 'three';

export function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function makeTexture(kind) {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
  const ctx = canvas.getContext('2d'); const random = rng(887);
  ctx.fillStyle = { grass: '#4c5840', asphalt: '#626663', roof: '#424c49', wall: '#b9baaa', brick: '#8b6550' }[kind]; ctx.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 14000; i++) {
    const light = random() > .5; ctx.fillStyle = light ? `rgba(215,217,171,${random()*.16})` : `rgba(8,18,10,${random()*.17})`;
    ctx.fillRect(random()*256, random()*256, kind === 'grass' ? 1 : 2, kind === 'grass' ? random()*6+1 : 2);
  }
  if (kind === 'roof' || kind === 'brick') {
    const h = kind === 'roof' ? 18 : 16, w = kind === 'roof' ? 38 : 42;
    for (let y = 0; y < 256; y += h) {
      ctx.fillStyle = kind === 'roof' ? '#232f2b' : '#b3a893'; ctx.fillRect(0, y, 256, 2);
      for (let x = -(y/h%2)*w/2; x < 256; x += w) {
        ctx.fillRect(x, y, 2, h); ctx.fillStyle = `rgba(210,215,192,${random()*.1})`; ctx.fillRect(x+2, y+2, w-2, h-3);
        ctx.fillStyle = kind === 'roof' ? '#28352e' : '#b3a893';
      }
    }
  }
  if (kind === 'wall') for (let y = 0; y < 256; y += 12) { ctx.fillStyle = '#9c9f90'; ctx.fillRect(0, y, 256, 1); ctx.fillStyle = '#d3d1c0'; ctx.fillRect(0, y+1, 256, 1); }
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping; texture.repeat.set(kind === 'grass' ? 16 : kind === 'asphalt' ? 9 : 2, kind === 'grass' ? 16 : kind === 'asphalt' ? 9 : 2);
  texture.anisotropy = 4; return texture;
}
export const createTextures = () => Object.fromEntries(['grass', 'asphalt', 'roof', 'wall', 'brick'].map(k => [k, makeTexture(k)]));