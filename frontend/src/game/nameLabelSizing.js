export const NAME_LABEL_TARGET_HEIGHT_PX = 42;
const NAME_LABEL_ASPECT = 1024 / 192;

// Converts the desired screen size into orthographic-world units.  The cap
// keeps an 18-character call sign inside narrow mobile viewports.
export function nameLabelScale(halfHeight, viewportHeight, viewportWidth) {
  const maxWidth = Math.max(1, Math.min(260, viewportWidth * .78));
  const heightPx = Math.min(NAME_LABEL_TARGET_HEIGHT_PX, maxWidth / NAME_LABEL_ASPECT);
  const heightWorld = heightPx * (2 * halfHeight) / Math.max(1, viewportHeight);
  return { x: heightWorld * NAME_LABEL_ASPECT, y: heightWorld, heightPx };
}
