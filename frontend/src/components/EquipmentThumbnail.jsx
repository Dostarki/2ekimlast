const forms = {
  head: <><path d="M20 39c0-17 12-27 30-27s30 10 30 27v8H20z"/><path d="M28 30h44"/></>,
  body: <><path d="M30 14h40l12 20-9 45H27l-9-45z"/><path d="M38 14v20m24-20v20M33 48h34"/></>,
  legs: <><path d="M29 13h18l3 36-12 31H20l9-31zM53 13h18l9 36-12 31H50l3-31z"/></>,
  hands: <><path d="M31 28l10-10 7 8 2-13 8 2-2 13 7-8 8 8-12 16-18 4z"/></>,
  feet: <><path d="M19 48h36l9 13v12H18z"/><path d="M27 48v-20h19l9 33"/></>,
  backpack: <><rect x="24" y="15" width="52" height="67" rx="8"/><path d="M35 15V8h30v7M24 42h52M34 53h32v18H34z"/></>,
};

export function EquipmentThumbnail({ item, compact = false }) {
  if (!item) return null;
  const tier = Number(item.tier) || 1;
  return <svg className={`equipment-thumbnail tier-${tier} ${compact ? 'compact' : ''}`} viewBox="0 0 100 100" role="img" aria-label={`${item.name} thumbnail`}><g>{forms[item.slot]}</g></svg>;
}
