import { edgeClamp, minimapTransform, shortestAngle, smoothAngle } from './minimap';

test('all map objects share the movement-heading frame', () => {
  expect(minimapTransform(0, 10, 0)).toEqual({ x: 0, y: -10 });
  expect(minimapTransform(10, 0, Math.PI / 2).x).toBeCloseTo(0, 6);
  expect(minimapTransform(10, 0, Math.PI / 2).y).toBeCloseTo(-10, 6);
});
test('heading interpolation takes the short arc and bosses clamp at the edge', () => {
  expect(Math.abs(shortestAngle(Math.PI - .02, -Math.PI + .02))).toBeLessThan(.05);
  expect(smoothAngle(Math.PI - .02, -Math.PI + .02, .5)).toBeGreaterThan(Math.PI - .02);
  expect(edgeClamp({ x: 100, y: 0 }, 66)).toEqual({ x: 66, y: 0, clipped: true });
});

test('cardinal and diagonal movement headings rotate the shared local frame', () => {
  expect(minimapTransform(0, 12, 0)).toEqual({ x: 0, y: -12 });
  expect(minimapTransform(12, 0, Math.PI / 2).y).toBeCloseTo(-12, 6);
  expect(minimapTransform(0, -12, Math.PI).y).toBeCloseTo(-12, 6);
  expect(minimapTransform(-12, 0, -Math.PI / 2).y).toBeCloseTo(-12, 6);
  const diagonal = minimapTransform(8, 8, Math.PI / 4);
  expect(diagonal.x).toBeCloseTo(0, 6);
  expect(diagonal.y).toBeCloseTo(-Math.sqrt(128), 6);
});

test('edge clamping retains marker direction and short-arc smoothing crosses pi safely', () => {
  const marker = edgeClamp({ x: -90, y: 90 }, 66);
  expect(marker.clipped).toBe(true);
  expect(Math.hypot(marker.x, marker.y)).toBeCloseTo(66, 6);
  const next = smoothAngle(Math.PI - .01, -Math.PI + .01, .25);
  expect(Math.abs(shortestAngle(Math.PI - .01, next))).toBeLessThan(.02);
});
