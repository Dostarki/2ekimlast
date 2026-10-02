import { nameLabelScale } from './nameLabelSizing';

describe('name label orthographic sizing', () => {
  test('keeps readable CSS height at all supported zoom levels', () => {
    const viewport = { width: 1280, height: 720 };
    const scales = [4, 24, 40].map(zoom => nameLabelScale(zoom, viewport.height, viewport.width));
    expect(scales.map(scale => scale.heightPx)).toEqual([42, 42, 42]);
    expect(scales[2].y / scales[0].y).toBeCloseTo(10);
    // The screen-space calculation is heightWorld / (2 * cameraHalfHeight / viewportHeight).
    scales.forEach((scale, index) => {
      expect(scale.y * viewport.height / (2 * [4, 24, 40][index])).toBeCloseTo(42);
    });
  });

  test('caps label width on narrow mobile viewports', () => {
    const scale = nameLabelScale(40, 640, 240);
    expect(scale.heightPx * (1024 / 192)).toBeCloseTo(240 * .78);
  });
});
