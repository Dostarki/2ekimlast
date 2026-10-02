// Generates isolated Early styles from the imported repo without altering its design.
const fs = require('fs');
const path = require('path');
const postcss = require('../frontend/node_modules/postcss');
const dir = path.resolve(__dirname, '../frontend/src/early');
const files = ['index.css', 'App.css', 'branding.css', 'admin.css'];
const output = files.map(file => {
  const root = postcss.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
  root.walkAtRules('tailwind', node => node.remove());
  root.walkAtRules('layer', node => node.replaceWith(...node.nodes));
  root.walkRules(rule => {
    let parent = rule.parent;
    while (parent) {
      if (parent.type === 'atrule' && /keyframes$/.test(parent.name)) return;
      parent = parent.parent;
    }
    rule.selectors = rule.selectors.map(selector => /^(?:\:root|html|body|#root)(?:\b|$)/.test(selector)
      ? selector.replace(/^(?:\:root|html|body|#root)/, '.early-app')
      : `.early-app ${selector}`);
  });
  const names = [];
  root.walkAtRules('keyframes', rule => { names.push(rule.params); rule.params = `early-${rule.params}`; });
  root.walkDecls(/^animation/, decl => { for (const name of names) decl.value = decl.value.replace(new RegExp(`\\b${name}\\b`, 'g'), `early-${name}`); });
  return root.toString();
}).join('\n');
fs.writeFileSync(path.join(dir, 'scoped.css'), output + '\n.early-app{position:fixed;inset:0;overflow-y:auto;overflow-x:hidden;background:#11150f;color:#e3e4d7;font-family:"IBM Plex Mono",monospace;font-size:14px;line-height:1.5;z-index:1}\n.early-app .site-header{flex-wrap:wrap}\n');
console.log('Early styles isolated.');