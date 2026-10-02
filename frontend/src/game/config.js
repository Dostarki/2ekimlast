export const WEAPONS = [
  {id:'glock18',name:'Glock 18',type:'AUTOMATIC PISTOL',tag:'STARTER',damage:18,speed:98,range:38,mag:17,rate:.065,kind:'bullet'},
  {id:'ak47',name:'AK-47',type:'ASSAULT RIFLE',tag:'CLASSIC POWER',damage:35,speed:71,range:72,mag:30,rate:.10,kind:'bullet'},
  {id:'ak117',name:'AK-117',type:'ASSAULT RIFLE',tag:'HIGH FIRE RATE',damage:26,speed:95,range:62,mag:35,rate:.075,kind:'bullet'},
  {id:'ak107',name:'AK-107',type:'ASSAULT RIFLE',tag:'BALANCED RECOIL',damage:30,speed:87,range:82,mag:30,rate:.09,kind:'bullet'},
  {id:'shotgun',name:'AA-12',type:'AUTOMATIC SHOTGUN',tag:'CLOSE RANGE',damage:126,speed:26,range:25,mag:8,rate:.30,kind:'bullet'},
  {id:'m4',name:'M4A1',type:'ASSAULT RIFLE',tag:'PRECISION FIRE',damage:28,speed:90,range:85,mag:30,rate:.085,kind:'bullet'},
  {id:'rocket',name:'RPG-7',type:'ROCKET LAUNCHER',tag:'EXPLOSIVE WARHEAD',damage:330,speed:9,range:110,mag:1,rate:1.1,kind:'rocket'},
  {id:'minigun',name:'M134',type:'MINIGUN',tag:'CONTINUOUS FIRE',damage:24,speed:100,range:75,mag:150,rate:.05,kind:'bullet'},
  {id:'flamethrower',name:'FLAME-21',type:'FLAMETHROWER',tag:'CLOSE-RANGE FLAME',damage:13.5,speed:71,range:9,mag:100,rate:.10,kind:'flame'},
  {id:'lava',name:'LAVA-6',type:'LAVA LAUNCHER',tag:'LINGERING FIRE',damage:67.5,speed:15,range:40,mag:6,rate:.65,kind:'lava'},
];
export const WEAPON_MAP = Object.fromEntries(WEAPONS.map(w=>[w.id,w]));
