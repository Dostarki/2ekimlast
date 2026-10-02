import math
from functools import lru_cache
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from pathfinding.finder.finder import ExecutionRunsException, ExecutionTimeException
from world import enemy_free, enemy_move, wall_distance

CELL = 1.5


@lru_cache(maxsize=90000)
def walkable(x, z):
    return int(enemy_free(x*CELL, z*CELL, .72))


def path_to(enemy, target):
    sx, sz = round(enemy['x']/CELL), round(enemy['z']/CELL)
    dx, dz = target['x']-enemy['x'], target['z']-enemy['z']
    distance = max(.01, math.hypot(dx, dz)); fraction = min(1, 42/distance)
    tx, tz = round((enemy['x']+dx*fraction)/CELL), round((enemy['z']+dz*fraction)/CELL)
    x0, z0 = min(sx, tx)-10, min(sz, tz)-10
    width, height = abs(tx-sx)+21, abs(tz-sz)+21
    matrix = [[walkable(x0+x, z0+z) for x in range(width)] for z in range(height)]
    # A distant sub-goal may land inside a house: choose a reachable nearby open cell.
    goal = min(((x, z) for z in range(height) for x in range(width) if matrix[z][x]), key=lambda p: (p[0]+x0-tx)**2+(p[1]+z0-tz)**2, default=None)
    if goal is None:
        return []
    matrix[sz-z0][sx-x0] = 1
    grid = Grid(matrix=matrix)
    finder = AStarFinder(diagonal_movement=DiagonalMovement.only_when_no_obstacle, max_runs=1600, time_limit=.008)
    try:
        path, _ = finder.find_path(grid.node(sx-x0, sz-z0), grid.node(*goal), grid)
    except (ExecutionRunsException, ExecutionTimeException):
        return []
    return [(node.x*CELL+x0*CELL, node.y*CELL+z0*CELL) for node in path[1:]]


def chase(game, enemy, target, speed, dt, now):
    x, z = target['x'], target['z']
    if wall_distance(enemy['x'], enemy['z'], x, z) < .98:
        if now >= enemy.get('next_path', 0) and game.path_budget > 0:
            game.path_budget -= 1
            enemy['path'] = path_to(enemy, target)
            enemy['next_path'] = now+2
        path = enemy.get('path', [])
        while path and math.hypot(path[0][0]-enemy['x'], path[0][1]-enemy['z']) < .65:
            path.pop(0)
        if path:
            x, z = path[0]
    else:
        enemy.pop('path', None)
    dx, dz = x-enemy['x'], z-enemy['z']; distance = math.hypot(dx, dz)
    step = min(distance, speed*dt)
    enemy['angle'] = math.atan2(dx, dz)
    enemy_move(enemy, dx/max(.001, distance)*step, dz/max(.001, distance)*step)
