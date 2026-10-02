import { box, rounded } from './characterParts';

const tierColor = tier => ['#5d6655', '#697957', '#8f9a6a'][Math.max(0, (tier || 1) - 1)];

// Articulated equipment: it deliberately stays out of mergeBody so rigs retain it.
export function addEquipmentModel({ body, head, legs, knees, arms }, equipped = {}) {
  const item = slot => equipped[slot] || '';
  const tier = slot => Number((item(slot).match(/_t(\d)/) || [])[1] || 1);
  if (item('head')) { rounded(head, 0, 2.16, 0, .48, .18, .48, tierColor(tier('head')), .06); box(head, 0, 2.08, .25, .30, .05, .06, '#20251e'); }
  if (item('body')) { rounded(body, 0, 1.35, .25, .58, .62, .17, tierColor(tier('body')), .04); box(body, 0, 1.22, .36, .40, .26, .05, '#263025'); }
  if (item('backpack')) { rounded(body, 0, 1.37, -.30, .46, .62, .20, tierColor(tier('backpack')), .04); box(body, 0, 1.44, -.42, .28, .18, .03, '#20271f'); }
  legs.forEach((leg, i) => {
    if (item('legs')) { rounded(leg, 0, -.18, .12, .22, .29, .08, tierColor(tier('legs')), .025); rounded(knees[i], 0, -.16, .14, .25, .18, .08, tierColor(tier('legs')), .025); }
    if (item('feet')) box(knees[i], 0, -.55, .08, .22, .12, .39, tierColor(tier('feet')));
  });
  if (item('hands')) arms.forEach(arm => rounded(arm, 0, -.52, .02, .16, .14, .18, tierColor(tier('hands')), .035));
}
