export const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
export const shortestAngle = (from, to) => Math.atan2(Math.sin(to - from), Math.cos(to - from));
export const smoothAngle = (from, to, amount) => from + shortestAngle(from, to) * clamp(amount, 0, 1);

// In this radar frame the player is at the origin and movement heading points up.
export function minimapTransform(dx, dz, heading, scale = 1) {
  const c = Math.cos(heading), s = Math.sin(heading);
  return { x: (c * dx - s * dz) * scale, y: (-s * dx - c * dz) * scale };
}

export function edgeClamp(point, radius) {
  const length = Math.hypot(point.x, point.y);
  return length > radius ? { x: point.x / length * radius, y: point.y / length * radius, clipped: true } : { ...point, clipped: false };
}
