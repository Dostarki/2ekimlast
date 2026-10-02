/** Display-only damage formatting. Combat values remain authoritative on the server. */
export function formatDamage(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? String(Math.max(0, Math.trunc(amount))) : '0';
}
