export const EQUIPMENT_SLOTS = [
  { id: 'head', name: 'HEAD', icon: 'shield' },
  { id: 'body', name: 'BODY', icon: 'shield' },
  { id: 'legs', name: 'LEGS', icon: 'shield' },
  { id: 'hands', name: 'HANDS', icon: 'crosshair' },
  { id: 'feet', name: 'FEET', icon: 'zap' },
  { id: 'backpack', name: 'BACKPACK', icon: 'backpack' },
];

export const EQUIPMENT_CATALOG = {
  // Head
  helm_t1: { id: 'helm_t1', name: 'Tactical Helmet', slot: 'head', tier: 1, levelReq: 3, statLabel: '+3 Armor', desc: 'Protective headgear with lightweight steel reinforcement.' },
  helm_t2: { id: 'helm_t2', name: 'Composite Helmet', slot: 'head', tier: 2, levelReq: 15, statLabel: '+6 Armor', desc: 'Advanced protective helmet with ceramic layering.' },
  helm_t3: { id: 'helm_t3', name: 'Heavy Ballistic Helmet', slot: 'head', tier: 3, levelReq: 30, statLabel: '+9 Armor', desc: 'Top-tier ballistic composite head armor.' },

  // Body
  vest_t1: { id: 'vest_t1', name: 'Light Assault Vest', slot: 'body', tier: 1, levelReq: 3, statLabel: '+6 Armor', desc: 'Tactical vest offering baseline ballistic protection.' },
  vest_t2: { id: 'vest_t2', name: 'Tactical Plate Carrier', slot: 'body', tier: 2, levelReq: 15, statLabel: '+12 Armor', desc: 'Body armor equipped with ceramic ballistic plates.' },
  vest_t3: { id: 'vest_t3', name: 'Heavy Assault Vest', slot: 'body', tier: 3, levelReq: 30, statLabel: '+18 Armor', desc: 'Composite body armor built for extreme combat.' },

  // Legs
  pants_t1: { id: 'pants_t1', name: 'Reinforced Pants', slot: 'legs', tier: 1, levelReq: 3, statLabel: '+3 Armor', desc: 'Durable pants woven with protective Kevlar fibers.' },
  pants_t2: { id: 'pants_t2', name: 'Combat Pants', slot: 'legs', tier: 2, levelReq: 15, statLabel: '+6 Armor', desc: 'Tactical combat pants with reinforced joint pads.' },
  pants_t3: { id: 'pants_t3', name: 'Armored Assault Pants', slot: 'legs', tier: 3, levelReq: 30, statLabel: '+9 Armor', desc: 'Heavy lower armor fitted with composite leg plates.' },

  // Hands
  gloves_t1: { id: 'gloves_t1', name: 'Tactical Shooting Gloves', slot: 'hands', tier: 1, levelReq: 3, statLabel: '-2% Reload', desc: 'Lightweight gloves enhancing weapon grip and reload speed.' },
  gloves_t2: { id: 'gloves_t2', name: 'Quick-Draw Gloves', slot: 'hands', tier: 2, levelReq: 15, statLabel: '-4% Reload', desc: 'Combat gloves improving weapon handling and reload speed.' },
  gloves_t3: { id: 'gloves_t3', name: 'Precision Composite Gloves', slot: 'hands', tier: 3, levelReq: 30, statLabel: '-6% Reload', desc: 'Ergonomic tactical gloves for maximum reload speed.' },

  // Feet
  boots_t1: { id: 'boots_t1', name: 'Light Patrol Boots', slot: 'feet', tier: 1, levelReq: 3, statLabel: '+1% Speed', desc: 'Flexible, wear-resistant all-terrain patrol boots.' },
  boots_t2: { id: 'boots_t2', name: 'Rapid Response Boots', slot: 'feet', tier: 2, levelReq: 15, statLabel: '+2% Speed', desc: 'Tactical boots engineered for quick repositioning.' },
  boots_t3: { id: 'boots_t3', name: 'Tactical Assault Boots', slot: 'feet', tier: 3, levelReq: 30, statLabel: '+3% Speed', desc: 'Engineered for maximum sprint mobility on rough terrain.' },

  // Backpack
  pack_t1: { id: 'pack_t1', name: 'Compact Backpack', slot: 'backpack', tier: 1, levelReq: 3, statLabel: '+3% Stamina', desc: 'Balances load distribution to boost stamina recovery.' },
  pack_t2: { id: 'pack_t2', name: 'Field Ops Pack', slot: 'backpack', tier: 2, levelReq: 15, statLabel: '+6% Stamina', desc: 'Ergonomic military pack designed for sustained operations.' },
  pack_t3: { id: 'pack_t3', name: 'Expedition Pack', slot: 'backpack', tier: 3, levelReq: 30, statLabel: '+9% Stamina', desc: 'High-capacity tactical pack for peak stamina recovery.' },
};

export const CRAFT_MATERIALS = [
  // Fabrics
  { id: 'fabric_t1', name: 'Ballistic Fabric', family: 'fabric', tier: 1 },
  { id: 'fabric_t2', name: 'Aramid Fiber', family: 'fabric', tier: 2 },
  { id: 'fabric_t3', name: 'Composite Fiber', family: 'fabric', tier: 3 },

  // Plates
  { id: 'plate_t1', name: 'Steel Plate', family: 'plate', tier: 1 },
  { id: 'plate_t2', name: 'Ceramic Plate', family: 'plate', tier: 2 },
  { id: 'plate_t3', name: 'Composite Plate', family: 'plate', tier: 3 },

  // Bindings
  { id: 'binding_t1', name: 'Nylon Strap', family: 'binding', tier: 1 },
  { id: 'binding_t2', name: 'Reinforced Binding', family: 'binding', tier: 2 },
  { id: 'binding_t3', name: 'Titanium Binding', family: 'binding', tier: 3 },

  // Mechanisms
  { id: 'mechanism_t1', name: 'Simple Mechanism', family: 'mechanism', tier: 1 },
  { id: 'mechanism_t2', name: 'Precision Mechanism', family: 'mechanism', tier: 2 },
  { id: 'mechanism_t3', name: 'Micro Mechanism', family: 'mechanism', tier: 3 },

  // Calibration Cartridges
  { id: 'calibration_t1', name: 'T1 Calibration Cartridge', family: 'calibration', tier: 1 },
  { id: 'calibration_t2', name: 'T2 Calibration Cartridge', family: 'calibration', tier: 2 },
  { id: 'calibration_t3', name: 'T3 Calibration Cartridge', family: 'calibration', tier: 3 },
];

export const SOLDIERS_CATALOG = [
  {
    tier: 1,
    name: 'Soldier S1 (Recruit)',
    role: 'Entry Support',
    hp: 120,
    weapon: 'Glock 18',
    damageMultiplier: '60%',
    fireRate: '0.45s',
    range: '14m',
    price: 500,
    levelReq: 1,
    desc: 'Provides covering sidearm fire. Protects owner at close quarters.',
  },
  {
    tier: 2,
    name: 'Soldier S2 (Patrol)',
    role: 'Shotgun Guardian',
    hp: 160,
    weapon: 'Shotgun',
    damageMultiplier: '75%',
    fireRate: '0.70s',
    range: '16m',
    price: 1000,
    levelReq: 10,
    desc: 'Delivers high point-blank crowd damage in close-range combat.',
  },
  {
    tier: 3,
    name: 'Soldier S3 (Rifleman)',
    role: 'Automatic Rifleman',
    hp: 220,
    weapon: 'AK-47',
    damageMultiplier: '85%',
    fireRate: '0.16s',
    range: '20m',
    price: 2000,
    levelReq: 20,
    desc: 'Suppresses hostile targets at medium range with sustained rifle bursts.',
  },
  {
    tier: 4,
    name: 'Soldier S4 (Operator)',
    role: 'Rapid Mobility SMG',
    hp: 300,
    weapon: 'Vector SMG',
    damageMultiplier: '95%',
    fireRate: '0.11s',
    range: '22m',
    price: 3500,
    levelReq: 30,
    desc: 'Eliminates agile targets rapidly with blistering submachine fire rate.',
  },
  {
    tier: 5,
    name: 'Soldier S5 (Elite)',
    role: 'Heavy Support MG',
    hp: 420,
    weapon: 'M249 Heavy MG',
    damageMultiplier: '110%',
    fireRate: '0.09s',
    range: '25m',
    price: 5500,
    levelReq: 40,
    desc: 'Peak-tier mercenary unit boasting maximum HP, accuracy, and engagement range.',
  },
];
