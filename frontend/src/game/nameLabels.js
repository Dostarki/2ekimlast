import * as THREE from 'three';
import { nameLabelScale } from './nameLabelSizing';

export function updateNameLabelScale(sprite, halfHeight, viewportHeight, viewportWidth) {
  if (!sprite) return;
  const scale = nameLabelScale(halfHeight, viewportHeight, viewportWidth);
  sprite.scale.set(scale.x, scale.y, 1);
  sprite.userData.cssHeight = scale.heightPx;
}

export function nameLabel(group, name, id, scene) {
  if (group.userData.labelName === name && group.userData.nameLabel) return;
  const previous = group.userData.nameLabel;
  if (previous) {
    if (previous.material?.map) previous.material.map.dispose();
    previous.material?.dispose();
    previous.removeFromParent();
  }
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 192;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.font = '600 68px "Barlow Condensed", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const width = Math.min(980, ctx.measureText(name).width + 80);
  ctx.fillStyle = 'rgba(10,18,13,.8)';
  ctx.fillRect((1024 - width) / 2, 30, width, 130);
  ctx.fillStyle = '#eef4dc';
  ctx.fillText(name, 512, 96, 920);

  const texture = new THREE.CanvasTexture(canvas);
  texture.generateMipmaps = false;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;

  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
    depthTest: false,
    fog: false
  }));
  sprite.renderOrder = 999;
  // Initial scale is replaced by GameRenderer's camera-aware projection pass.
  updateNameLabelScale(sprite, 24, 1080, 1920);
  sprite.userData.nameLabel = true;
  sprite.userData.testId = `player-name-label-${id}`;

  const parent = scene || group;
  parent.add(sprite);
  group.userData.nameLabel = sprite;
  group.userData.labelName = name;
  sprite.position.set(group.position.x, 3.2, group.position.z);
}
