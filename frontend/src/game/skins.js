export const SKINS = [
  { id: 'soldier', name: 'Soldier', detail: 'Camouflage · Tactical vest', shirt: '#566548', pants: '#414b35', vest: '#303a2d', skin: '#caa17b', hair: '#302920', accent: '#a3b17b', gloves: true },
  { id: 'fbi', name: 'FBI', detail: 'Operations · Federal unit', shirt: '#253447', pants: '#222b36', vest: '#141d2a', skin: '#d2ad8c', hair: '#272321', accent: '#edc95a', gloves: true },
  { id: 'civilian', name: 'Civilian', detail: 'Button-down · Denim jeans', shirt: '#a14d3d', pants: '#465f78', skin: '#d1a17d', hair: '#50392a', accent: '#cd7968', rolled: true },
  { id: 'terrorist', name: 'Insurgent', detail: 'Ski mask · Bandolier', shirt: '#79746a', pants: '#4d5140', skin: '#bd957c', hair: '#242524', accent: '#b8afa0', gloves: true },
  { id: 'gang_male', name: 'Gangster (M)', detail: 'Tracksuit · Gold chain', shirt: '#274c42', pants: '#242c2b', skin: '#a97653', hair: '#1d211e', accent: '#65a48d' },
  { id: 'gang_female', name: 'Gangster (F)', detail: 'Burgundy jacket · Ponytail', shirt: '#80364e', pants: '#30303b', skin: '#d4ab8d', hair: '#28212a', accent: '#d27b95', female: true },
];
export const SKIN_MAP = Object.fromEntries(SKINS.map(s => [s.id, s]));
export const getSkin = id => SKIN_MAP[id] || SKINS[0];
export const skinTestId = id => id.replaceAll('_', '-');