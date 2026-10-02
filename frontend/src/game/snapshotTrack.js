// Timestamped remote motion: smooth jitter, short bounded extrapolation, no endless drift.
export class SnapshotTrack {
  constructor() { this.samples = []; }
  push(entity, time) {
    const last = this.samples[this.samples.length - 1];
    if (last && time <= last.time) return;
    if (last && Math.hypot(entity.x - last.x, entity.z - last.z) > 8) this.samples = [];
    this.samples.push({ x: entity.x, z: entity.z, angle: entity.angle, time });
    if (this.samples.length > 6) this.samples.shift();
  }
  sample(time) {
    const list = this.samples;
    if (!list.length) return null;
    if (time <= list[0].time) return list[0];
    for (let i = 1; i < list.length; i++) {
      const a = list[i - 1], b = list[i];
      if (time <= b.time) {
        const t = (time - a.time) / Math.max(1, b.time - a.time);
        const angle = a.angle + Math.atan2(Math.sin(b.angle - a.angle), Math.cos(b.angle - a.angle)) * t;
        return { x: a.x + (b.x - a.x) * t, z: a.z + (b.z - a.z) * t, angle };
      }
    }
    const last = list[list.length - 1], previous = list[list.length - 2];
    if (!previous) return last;
    const t = Math.min(80, Math.max(0, time - last.time)) / Math.max(1, last.time - previous.time);
    return { x: last.x + (last.x - previous.x) * t, z: last.z + (last.z - previous.z) * t, angle: last.angle };
  }
}