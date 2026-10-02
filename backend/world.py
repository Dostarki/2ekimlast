import random
import pymunk

WEAPONS = {
    'glock18': {'name':'Glock 18','damage':18,'mag':17,'rate':.065,'range':38,'reload':1.5,'spread':.04,'pellets':1,'kind':'bullet','reserve':102,'infinite_reserve':True},
    'ak47': {'name':'AK-47','damage':35,'mag':30,'rate':.10,'range':72,'reload':2.1,'spread':.018,'pellets':1,'kind':'bullet','reserve':180},
    'ak117': {'name':'AK-117','damage':26,'mag':35,'rate':.075,'range':62,'reload':1.8,'spread':.028,'pellets':1,'kind':'bullet','reserve':210},
    'ak107': {'name':'AK-107','damage':30,'mag':30,'rate':.09,'range':82,'reload':2,'spread':.009,'pellets':1,'kind':'bullet','reserve':180},
    'shotgun': {'name':'AA-12','damage':18,'mag':8,'rate':.3,'range':25,'reload':2.6,'spread':.17,'pellets':7,'kind':'bullet','reserve':64},
    'm4': {'name':'M4A1','damage':28,'mag':30,'rate':.085,'range':85,'reload':1.9,'spread':.012,'pellets':1,'kind':'bullet','reserve':180},
    'rocket': {'name':'RPG-7','damage':330,'mag':1,'rate':1.1,'range':110,'reload':2.8,'spread':0,'pellets':1,'kind':'rocket','reserve':10},
    'minigun': {'name':'M134','damage':24,'mag':150,'rate':.05,'range':75,'reload':3.8,'spread':.045,'pellets':1,'kind':'bullet','reserve':450},
    'flamethrower': {'name':'FLAME-21','damage':13.5,'mag':100,'rate':.1,'range':9,'reload':3,'spread':.3,'pellets':1,'kind':'flame','reserve':300},
    'lava': {'name':'LAVA-6','damage':67.5,'mag':6,'rate':.65,'range':40,'reload':2.5,'spread':0,'pellets':1,'kind':'lava','reserve':36},
}
space = pymunk.Space()
rng = random.Random(4178)
chunks, buildings = [], []


def add_barrier(x, z, w, d):
    shape = pymunk.Poly(space.static_body, [(x-w/2,z-d/2),(x+w/2,z-d/2),(x+w/2,z+d/2),(x-w/2,z+d/2)])
    space.add(shape)
    return {'x':x,'z':z,'w':w,'d':d}


for cx in range(-10,10):
    for cz in range(-10,10):
        houses, trees, barriers = [], [], []
        for index,(ox,oz) in enumerate([(25,25),(56,25),(25,56),(56,56)]):
            x,z = cx*80+ox+rng.randint(-3,3),cz*80+oz+rng.randint(-3,3)
            w,d = rng.randint(15,21),rng.randint(12,17)
            enterable = index == 0 or (cx == 0 and cz == 0 and index < 3)
            kind = ['gas','hotel','home'][(cx+cz+index)%3] if enterable else 'house'
            h = {'id':f'{cx}:{cz}:{index}','x':x,'z':z,'w':w,'d':d,'h':rng.choice([5.5,6,8]),'style':rng.randrange(5),'enterable':enterable,'kind':kind}
            if enterable:
                h['h'] = 3.6 if kind != 'hotel' else 4.5
                h['name'] = {'gas':'WESTFALL GAS STATION','hotel':'WESTFALL HOTEL','home':'ABANDONED HOUSE'}[kind]
                h['door'] = {'x':x,'z':z-d/2,'width':3.2}
                h['walls'] = [add_barrier(x-w/2,z,.45,d),add_barrier(x+w/2,z,.45,d),add_barrier(x,z+d/2,w,.45)]
                wing = (w-3.2)/2
                h['walls'] += [add_barrier(x-(w+3.2)/4,z-d/2,wing,.45),add_barrier(x+(w+3.2)/4,z-d/2,wing,.45)]
                if kind == 'hotel':
                    h['walls'] += [add_barrier(x-w*.29,z+1,w*.42,.3),add_barrier(x+w*.29,z+1,w*.42,.3)]
                # Furniture is cover as well as a movement obstacle; front corridor stays open.
                furniture = [{'x':x+w*.25,'z':z+d*.15,'w':w*.27,'d':1.2,'kind':'counter'}]
                if kind == 'home': furniture.append({'x':x-w*.25,'z':z+d*.22,'w':3.2,'d':1.4,'kind':'sofa'})
                if kind == 'hotel': furniture += [{'x':x-w*.26,'z':z+d*.3,'w':2.6,'d':3.1,'kind':'bed'}]
                if kind == 'gas': furniture += [{'x':x-w*.28,'z':z+d*.23,'w':1.1,'d':4,'kind':'shelf'}]
                h['furniture'] = furniture
                barriers += h['walls']
                for f in furniture: barriers.append(add_barrier(f['x'],f['z'],f['w'],f['d']))
                buildings.append(h)
            else:
                barriers.append(add_barrier(x,z,w,d))
            houses.append(h)
        for _ in range(13):
            x,z = cx*80+rng.randint(12,69),cz*80+rng.randint(12,69)
            if not any(abs(x-h['x']) < h['w']/2+2 and abs(z-h['z']) < h['d']/2+2 for h in houses):
                trees.append({'x':x,'z':z,'s':round(rng.uniform(.8,1.5),2),'type':rng.randrange(2)})
        chunks.append({'id':f'{cx},{cz}','x':cx*80,'z':cz*80,'houses':houses,'trees':trees,'barriers':barriers,'seed':rng.randrange(999999)})

WORLD = {'size':1600,'block':80,'seed':4178,'chunks':chunks,
         'safe_zone': {'x': 0, 'z': 0, 'radius': 14}}
BUILDING_GRID = {}
for b in buildings: BUILDING_GRID.setdefault((int(b['x']//80),int(b['z']//80)),[]).append(b)


SAFE_ZONE_RADIUS = 14


def interior_at(x,z):
    for h in BUILDING_GRID.get((int(x//80),int(z//80)),[]):
        if abs(x-h['x']) < h['w']/2-.3 and abs(z-h['z']) < h['d']/2-.3: return h['name']
    return None


def safe_zone_at(x, z):
    """Return whether a survivor is in the permanent sanctuary.

    The central plaza is the safe spawn area.  Enterable buildings are also
    sanctuaries, so infected never cross a doorway to attack a player inside.
    """
    return x*x + z*z <= SAFE_ZONE_RADIUS*SAFE_ZONE_RADIUS or interior_at(x, z) is not None


def free(x,z,radius=.65):
    return -788 < x < 788 and -788 < z < 788 and not space.point_query((x,z),radius,pymunk.ShapeFilter())


def move(entity,dx,dz):
    if free(entity['x']+dx,entity['z']): entity['x'] += dx
    if free(entity['x'],entity['z']+dz): entity['z'] += dz


def enemy_free(x, z, radius=.65):
    # Keep the whole enemy collider outside the sanctuary boundary, not only
    # its centre point.  Interiors are completely off-limits to enemies.
    return free(x, z, radius) and x*x + z*z > (SAFE_ZONE_RADIUS + radius)**2 and interior_at(x, z) is None


def enemy_move(entity, dx, dz, radius=.65):
    if enemy_free(entity['x']+dx, entity['z']+dz, radius): entity['x'] += dx
    if enemy_free(entity['x'], entity['z']+dz, radius): entity['z'] += dz


def wall_distance(x,z,tx,tz):
    hit = space.segment_query_first((x,z),(tx,tz),.04,pymunk.ShapeFilter())
    return hit.alpha if hit else 1.0
