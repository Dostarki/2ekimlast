import * as THREE from 'three';
import { box, rounded, limb, material } from './characterParts';

const labels = new Map();
function label(group, text, x, y, z, w, h, back = false) {
  if (!labels.has(text)) {
    const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 96;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#141d2a'; ctx.fillRect(0, 0, 256, 96);
    ctx.fillStyle = '#f1d469'; ctx.font = 'bold 76px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 128, 50);
    const map = new THREE.CanvasTexture(canvas); map.colorSpace = THREE.SRGBColorSpace;
    labels.set(text, new THREE.MeshLambertMaterial({ map }));
  }
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), labels.get(text));
  mesh.position.set(x, y, z); if (back) mesh.rotation.y = Math.PI; group.add(mesh);
}
function crown(group, color, cap = false, backwards = false) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(cap ? .247 : .274, 16, 10, 0, Math.PI*2, 0, Math.PI*.55), material(color));
  mesh.position.set(0, 2.015, -.018); group.add(mesh);
  if (cap) rounded(group, 0, 2.047, backwards ? -.24 : .24, .36, .045, .27, color, .02);
}
function chain(group) {
  const points = [[-.16,1.64,.17],[-.15,1.48,.255],[0,1.30,.31],[.15,1.48,.255],[.16,1.64,.17]].map(p => new THREE.Vector3(...p));
  const mesh = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 20, .016, 6, false), material('#d9b952', .4)); group.add(mesh);
}
export function dressCharacter(body, head, legs, knees, style) {
  const id = style.id;
  box(body, 0, .9, 0, style.female ? .57 : .65, .065, .39, '#232623');
  if (style.vest) {
    rounded(body, 0, 1.28, .21, .56, .54, .14, style.vest);
    for (const x of [-.19, 0, .19]) rounded(body, x, 1.17, .30, .15, .20, .09, style.vest, .014);
    rounded(body, 0, 1.28, -.23, .53, .52, .12, style.vest);
  }
  if (id === 'soldier') {
    crown(head, '#455139'); box(head, 0, 2.01, .23, .34, .07, .06, '#242e25');
    rounded(body, 0, 1.23, -.30, .44, .53, .24, '#485039');
    legs.forEach((leg, i) => {
      for (let j = 0; j < 3; j++) rounded(leg, (j%2 ? -.055 : .055), -.10-j*.11, .13, .12, .08, .035, j%2 ? '#858366' : '#2e3a28', .012);
      rounded(knees[i], 0, -.10, .13, .20, .16, .06, '#576143');
    });
  } else if (id === 'fbi') {
    crown(head, style.shirt, true); label(body, 'FBI', 0, 1.43, .293, .36, .13); label(body, 'FBI', 0, 1.42, -.30, .43, .17, true);
    label(head, 'FBI', 0, 2.145, .197, .21, .08); rounded(head, .235, 1.95, 0, .07, .15, .10, '#14191f');
  } else if (id === 'civilian') {
    crown(head, style.hair); rounded(body, 0, 1.26, -.29, .43, .50, .24, '#8c7956');
    for (const x of [-.20, 0, .20]) box(body, x, 1.29, .231, .022, .58, .014, '#63362e');
    for (const y of [1.08, 1.23, 1.39, 1.52]) box(body, 0, y, .237, .50, .023, .015, '#d39676');
    rounded(body, .14, 1.43, .25, .14, .12, .018, '#a65540', .01);
  } else if (id === 'terrorist') {
    crown(head, '#26292a'); rounded(head, 0, 1.88, .13, .39, .19, .24, '#292c2d');
    for (const x of [-.15,.15]) rounded(head, x, 2.015, .17, .09, .19, .12, '#292c2d');
    const strap = box(body, 0, 1.31, .25, .11, .72, .05, '#34352c'); strap.rotation.z = -.65;
    for (let i=0; i<6; i++) { const bullet = rounded(body, -.19+i*.076, 1.55-i*.09, .29, .045, .13, .045, '#ad975e', .012); bullet.rotation.z = -.65; }
  } else if (id === 'gang_male') {
    crown(head, '#263b32', true, true); chain(body);
    box(body, 0, 1.30, .232, .026, .60, .015, '#d2d2bb');
    legs.forEach(leg => box(leg, .135, -.22, 0, .018, .40, .10, '#d7d9c9'));
    knees.forEach(knee => box(knee, .12, -.19, 0, .018, .36, .10, '#d7d9c9'));
  } else {
    crown(head, style.hair);
    limb(head, 0, 1.91, -.28, .11, .48, style.hair); limb(head, 0, 1.62, -.31, .075, .32, style.hair);
    rounded(head, 0, 2.04, -.27, .17, .07, .12, style.shirt);
    rounded(body, 0, 1.34, .19, .23, .41, .05, '#d5cfbb');
    for (const side of [-1,1]) { const lapel = box(body, side*.16, 1.45, .225, .085, .29, .03, '#492332'); lapel.rotation.z = side*.25; }
    for (const side of [-1,1]) rounded(head, side*.22, 1.90, .04, .032, .065, .025, '#d3b254', .01);
  }
}