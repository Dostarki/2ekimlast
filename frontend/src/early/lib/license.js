import { toast } from '../components/ui/sonner';
import { numberLabel } from './api';

const portrait = ['000001111100000','000111111111000','001111111111100','001122222221100','001222222222100','000222222222000','000221222122000','000222222222000','000022222220000','000002222200000','000033333330000','003333333333300','033333333333330','333333333333333','333333333333333'];

export function drawLicense(canvas, agent, handle, profilePhoto = null) {
  const ctx = canvas.getContext('2d');
  canvas.width = 760; canvas.height = 900;
  ctx.fillStyle = '#c8ccba'; ctx.fillRect(0, 0, 760, 900);
  for (let i = 0; i < 6500; i++) {
    const x = (i * 37.79) % 760, y = (i * 81.47) % 900;
    ctx.fillStyle = i % 2 ? '#19241a09' : '#ffffff19'; ctx.fillRect(x, y, 2, 2);
  }
  ctx.strokeStyle = '#505c4960'; ctx.lineWidth = 1; ctx.strokeRect(26, 26, 708, 848);
  const text = (str, x, y, font, color = '#283329') => { ctx.font = font; ctx.fillStyle = color; ctx.fillText(str, x, y); };
  text('L A S T Z H O O D  /  S U R V I V O R  R E G I S T R Y', 55, 70, '16px "IBM Plex Mono", monospace');
  ctx.fillStyle = '#273228'; ctx.fillRect(54, 91, 652, 2);
  text('AGENT LICENSE', 54, 156, '800 58px "Barlow Condensed", sans-serif');
  text(numberLabel(agent?.number), 55, 194, '22px "IBM Plex Mono", monospace');
  text('GENESIS EDITION / 001', 424, 190, '15px "IBM Plex Mono", monospace');
  ctx.fillStyle = '#253027'; ctx.fillRect(55, 225, 360, 325);
  ctx.strokeStyle = '#6b7d6355';
  for (let x = 55; x < 415; x += 20) { ctx.beginPath(); ctx.moveTo(x, 225); ctx.lineTo(x, 550); ctx.stroke(); }
  for (let y = 225; y < 550; y += 20) { ctx.beginPath(); ctx.moveTo(55, y); ctx.lineTo(415, y); ctx.stroke(); }
  portrait.forEach((row, y) => [...row].forEach((pixel, x) => {
    if (pixel === '0') return;
    ctx.fillStyle = pixel === '1' ? '#a5af81' : pixel === '2' ? ((x + y) % 3 ? '#c4c99d' : '#849672') : ((x * y) % 4 ? '#768767' : '#a6b18c');
    ctx.fillRect(99 + x * 18, 254 + y * 18, 17, 17);
  }));
  if (profilePhoto) {
    // Keep the entire original profile photo visible (no face cropping), also in PNG exports.
    ctx.fillStyle = '#253027'; ctx.fillRect(55, 225, 360, 325);
    const scale = Math.min(330 / profilePhoto.naturalWidth, 300 / profilePhoto.naturalHeight);
    const width = profilePhoto.naturalWidth * scale;
    const height = profilePhoto.naturalHeight * scale;
    ctx.drawImage(profilePhoto, 55 + (360 - width) / 2, 225 + (325 - height) / 2, width, height);
    ctx.strokeStyle = '#798a66'; ctx.lineWidth = 1; ctx.strokeRect(55, 225, 360, 325);
  }
  text('IDENTITY', 450, 252, '14px "IBM Plex Mono", monospace');
  text('SELF-DECLARED', 450, 280, '600 17px "IBM Plex Mono", monospace');
  text('CELL', 450, 334, '14px "IBM Plex Mono", monospace');
  text(agent?.cell || '— . —', 450, 365, '500 24px "IBM Plex Mono", monospace');
  text('CLASS', 450, 416, '14px "IBM Plex Mono", monospace');
  text(agent?.agent_class || 'ENCRYPTED', 450, 446, '600 20px "IBM Plex Mono", monospace');
  text('TIER', 450, 500, '14px "IBM Plex Mono", monospace');
  text(agent?.tier || 'PENDING', 450, 530, '600 20px "IBM Plex Mono", monospace');
  text('@' + (agent?.handle || handle || 'unknown'), 54, 612, '700 43px "Barlow Condensed", sans-serif');
  text('ONE AGENT. ONE PLACE ON THE GRID.', 56, 646, '15px "IBM Plex Mono", monospace');
  ctx.save(); ctx.translate(555, 698); ctx.rotate(-.11); ctx.strokeStyle = '#81473d'; ctx.lineWidth = 3; ctx.strokeRect(-117, -25, 242, 54);
  text(agent ? 'ACCESS GRANTED' : 'AWAITING CLAIM', -100, 11, '700 26px "Barlow Condensed", sans-serif', '#81473d'); ctx.restore();
  ctx.fillStyle = '#283329';
  const seed = (agent?.ref_code || handle || 'PENDING').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);
  for (let i = 0, x = 57; x < 389; i++) { const w = 2 + ((i * 13 + seed) % 5); if (i % 2) ctx.fillRect(x, 708, w, 72); x += w; }
  text(agent?.ref_code || 'REGISTRATION PENDING', 56, 806, '15px "IBM Plex Mono", monospace');
  ctx.fillStyle = '#283329'; ctx.fillRect(54, 832, 652, 1);
  text('LastZhood', 55, 856, '600 16px "IBM Plex Mono", monospace');
  text(agent ? agent.created_at.slice(0, 10).replaceAll('-', '.') : 'EARLY ACCESS', 548, 856, '14px "IBM Plex Mono", monospace');
}

export async function saveLicense(canvas, handle) {
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('Card export unavailable.');
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = `LastZhood-${handle}-license.png`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export async function copyLicense(canvas, handle) {
  try {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!navigator.clipboard?.write || !window.ClipboardItem || !blob) throw new Error('Unsupported');
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
    toast.success('Agent card copied.');
  } catch (_) {
    try { await saveLicense(canvas, handle); toast.info('Image copying is unavailable here. Your card was downloaded instead.'); }
    catch (_) { toast.error('Could not export your card. Please try again.'); }
  }
}