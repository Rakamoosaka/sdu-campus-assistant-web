"""Building geometry, walking graph and place positions for floors 1-3.

Traced from the posted evacuation plans (docs/map-source/evacuation-plans/). The
photos were warped into one frame by scripts/stitch_evacuation_plans.py; the
coordinates below were read from those stitched references. North (Block H) is
up, the teaching blocks D-H branch west from the main corridor.

This is a schematic trace: walls are simplified, doors are approximate and the
drawing units are not metres.
"""
import math

WIDTH, HEIGHT = 800, 1660
DY = 20  # trace frame -> map frame

BLOCKS = 'DEFGH'
BLOCK_COLORS = {'D': '#833282', 'E': '#7b1f2b', 'F': '#2f3d7d', 'G': '#4c7a3a', 'H': '#2e6aa3'}
FACULTIES = {
    'D': ['Faculty of Law &', 'Social Sciences'],
    'E': ['Faculty of Education', '& Humanities'],
    'F': ['Faculty of Engineering', '& Natural Sciences'],
    'G': ['SDU Business School'],
    'H': [],
}

# Teaching block bands, from the corner fit used for stitching (k: D=0 ... H=4).
X_ROOT, X_END, X_ROOMS = 446.0, 263.0, 300.0      # spine side, far end, end-room wall
COLUMN = (448.0, 498.0)                             # rooms along the west side of the spine


def band(block):
    top = 327.5 + 216.5 * BLOCKS.index(block)
    f = lambda v: (1320 - v) * 1.2
    return {
        'south': (f(top + 46), f(top)),                       # long wing: classrooms
        'corridor': (f(top + 66), f(top + 46)),
        'north_root': (f(top + 108), f(top + 73)),            # angled wing at the spine
        'north_end': (f(top + 93), f(top + 67)),              # angled wing at the far end
        'corridor_y': f(top + 56),
    }


def lerp(a, b, t):
    return a + (b - a) * t


def north_wall(block, x):
    """South wall of the angled north wing at x (it narrows toward the end)."""
    b = band(block)
    t = (X_ROOT - x) / (X_ROOT - X_END)
    return lerp(b['north_root'][1], b['north_end'][1], t)


def north_top(block, x):
    b = band(block)
    t = (X_ROOT - x) / (X_ROOT - X_END)
    return lerp(b['north_root'][0], b['north_end'][0], t)


# Curved stairs sit in the gaps between blocks, just west of the spine column.
CURVED_STAIRS = {'HG': 210, 'GF': 464, 'FE': 730, 'ED': 985}

BOCHKAS = [(578, 835, 39), (623, 981, 51), (578, 1090, 39), (622, 1188, 52)]
SPIRAL = (605, 897, 17)

H_WING = [(562, 8), (705, 8), (718, 42), (692, 100), (635, 130), (590, 82), (562, 66)]
G_HALL = [(570, 300), (640, 226), (725, 345), (655, 400)]
CANTEEN = [(542, 472), (738, 472), (738, 540), (700, 600), (700, 665), (542, 665)]
WIFI = [(560, 1325), (640, 1400), (562, 1470), (485, 1397)]
C_HALL = [(470, 1245), (690, 1245), (748, 1335), (748, 1400), (700, 1440), (640, 1440),
          (562, 1478), (480, 1405), (470, 1390)]
LIBRARY = [(345, 1478), (478, 1465), (500, 1548), (360, 1568)]
FACADE = [(740, 470), (740, 540), (702, 600), (702, 700), (668, 745), (682, 790), (662, 812),
          (667, 905), (685, 965), (680, 1010), (675, 1060), (685, 1120), (700, 1180), (690, 1245)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def centroid(points):
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


class Layout:
    def __init__(self):
        self.shapes = {1: [], 2: [], 3: []}
        self.labels = []
        self.nodes, self.node_floors, self.edges = {}, {}, []
        self.places = {}   # map_key -> position/attachment (+ full record for generated places)

    # --- drawing -----------------------------------------------------------
    def shape(self, floor, kind, points=None, **extra):
        self.shapes[floor].append({'kind': kind, 'points': points, **extra})

    def label(self, text, x, y, floors=(1, 2, 3), **style):
        self.labels.append({'text': text, 'x': x, 'y': y, 'floors': list(floors), **style})

    # --- graph -------------------------------------------------------------
    def node(self, key, x, y, floor):
        self.nodes[key] = [round(x, 2), round(y, 2)]
        self.node_floors[key] = floor
        return key

    def edge(self, a, b, kind='corridor', label=''):
        self.edges.append({'a': a, 'b': b, 'kind': kind, 'label': label})

    def chain(self, keys):
        for a, b in zip(keys, keys[1:]):
            self.edge(a, b)

    # --- places ------------------------------------------------------------
    def place(self, key, x, y, floor, node, geometry=None, **record):
        self.places[key] = {'x': x, 'y': y, 'floor': floor, 'node': node,
                            'geometry': geometry, 'record': record or None}


def build():
    L = Layout()
    build_blocks(L)
    build_spine(L)
    build_floor1_east(L)
    build_floor2_east(L)
    build_floor3_east(L)
    build_south(L)
    build_vertical(L)
    build_labels(L)
    return shift(L)


# ---------------------------------------------------------------------------
# Teaching blocks D-H and the spine column
# ---------------------------------------------------------------------------

def classroom_slots(block):
    """Classroom rectangles in the long south wing, nearest the spine first."""
    if block == 'H':  # two large rooms on every floor in the plans
        edges = [X_ROOT, 373.0, X_ROOMS]
    else:             # four classrooms plus an end room
        width = (X_ROOT - X_ROOMS) / 4
        edges = [X_ROOT - i * width for i in range(5)]
    return [(edges[i + 1], edges[i]) for i in range(len(edges) - 1)]


def build_blocks(L):
    for block in BLOCKS:
        b = band(block)
        color = BLOCK_COLORS[block]
        s0, s1 = b['south']
        for floor in (1, 2, 3):
            wing_n = [(X_ROOT, b['north_root'][0]), (X_ROOT, b['north_root'][1]),
                      (X_END, b['north_end'][1]), (X_END, b['north_end'][0])]
            corridor = [(X_ROOT + 2, north_wall(block, X_ROOT)), (X_ROOT + 2, s0),
                        (X_END, s0), (X_END, north_wall(block, X_END))]
            L.shape(floor, 'plate', corridor)
            L.shape(floor, 'wing', wing_n, color=color)
            L.shape(floor, 'wing', rect(X_END, s0, X_ROOT, s1), color=color)
            # End room of the long wing and the end staircase of the angled wing.
            L.shape(floor, 'room', rect(X_END, s0, X_ROOMS, s1), color=color)
            L.shape(floor, 'stairs', [(X_END + 3, north_top(block, X_END) + 3), (X_ROOMS - 3, north_top(block, X_ROOMS) + 3),
                                      (X_ROOMS - 3, north_wall(block, X_ROOMS) - 3), (X_END + 3, north_wall(block, X_END) - 3)])
            # Angled wing rooms: two on floor 1, small offices above.
            parts = 2 if floor == 1 else 6
            edges = [lerp(X_ROOT, X_ROOMS, i / parts) for i in range(parts + 1)]
            for i in range(parts):
                xa, xb = edges[i + 1], edges[i]
                L.shape(floor, 'room', [(xb, north_top(block, xb)), (xb, north_wall(block, xb)),
                                        (xa, north_wall(block, xa)), (xa, north_top(block, xa))], color=color)
            if floor == 2:  # ring corridor around a light well
                y0 = north_wall(block, 310)
                L.shape(floor, 'void', [(436, north_wall(block, 436) + 3), (436, y0 + 9), (312, y0 + 9), (312, north_wall(block, 312) + 3)])
            # Block exit at the far end of the corridor.
            L.shape(floor, 'exit', [(X_END - 6, b['corridor_y'])])
            build_block_graph(L, block, floor)


def corridor_route_y(block, floor):
    b = band(block)
    # Floor 2 corridors pass the light well on its south side.
    return b['south'][0] - 6 if floor == 2 else b['corridor_y']


def build_block_graph(L, block, floor):
    b = band(block)
    y = corridor_route_y(block, floor)
    low = block.lower()
    root = L.node(f'f{floor}_{low}_root', 472, y, floor)
    stops = []  # (x, node key)
    for n, (xa, xb) in enumerate(classroom_slots(block), 1):
        key = f'{low}{floor}0{n}'
        cx = (xa + xb) / 2
        node = L.node(f'f{floor}_{low}_room_{n}', cx, y, floor)
        stops.append((cx, node))
        s0, s1 = b['south']
        L.place(key, cx, (s0 + s1) / 2, floor, node,
                geometry={'x': round(xa, 2), 'y': round(s0, 2), 'width': round(xb - xa, 2), 'height': round(s1 - s0, 2)},
                name=key.upper(), category='Classroom', block=f'Block {block}', floors=[floor],
                notes=('Room order confirmed; door positions unresolved.' if block == 'D' and floor == 1 else
                       'Position traced from the evacuation plan. The room number follows the D101 pattern '
                       '(01 nearest the main corridor) and is not individually verified; doors are approximate.'))
    if floor == 1:  # the two rooms of the angled wing (only D has reported numbers)
        for n, (xa, xb) in enumerate([(373.0, X_ROOT), (X_ROOMS, 373.0)], 5):
            cx = (xa + xb) / 2
            node = next((k for x, k in stops if abs(x - cx) < 3), None)
            if node is None:
                node = L.node(f'f1_{low}_north_{n}', cx, y, 1)
                stops.append((cx, node))
            if block == 'D':
                L.place(f'd10{n}', cx, (north_top(block, cx) + north_wall(block, cx)) / 2, 1, node,
                        geometry=None)
    if block in 'DFH':
        lift = L.node(f'f{floor}_{low}_lift', 355, y, floor)
        stops.append((355, lift))
    end = L.node(f'f{floor}_{low}_end', 281, y, floor)
    stops.append((281, end))
    stops.sort(key=lambda s: -s[0])
    L.chain([root] + [k for _, k in stops])


def build_spine(L):
    """Rooms along the west side of the main corridor, cut by each block corridor."""
    cuts = []
    for block in BLOCKS:
        b = band(block)
        cuts.append((b['north_root'][0], b['south'][1]))
    cuts.sort()
    for floor in (1, 2, 3):
        start = 0
        for top, bottom in cuts + [(1378, 1378)]:
            if top - start > 8:
                L.shape(floor, 'column', rect(COLUMN[0], start + 2, COLUMN[1], top - 2))
            start = bottom
        # Restroom cores at each block entrance (same layout on every floor).
        for block in BLOCKS:
            b = band(block)
            L.shape(floor, 'core', rect(COLUMN[0], b['south'][0] + 3, COLUMN[1] - 12, b['south'][1] - 3))
            L.shape(floor, 'core', rect(COLUMN[0], b['north_root'][0] + 3, COLUMN[1] - 12, north_wall(block, X_ROOT) - 3))
        for gap, yc in CURVED_STAIRS.items():
            if floor in (1, 2):
                L.shape(floor, 'curved_stairs', [(COLUMN[0], yc)], r=25)
    # Restroom places (floor 1, as catalogued).
    for block in BLOCKS:
        b = band(block)
        low = block.lower()
        root = f'f1_{low}_root'
        L.place(f'{low}_restroom', 466, (b['south'][0] + b['south'][1]) / 2, 1, root)
        L.place(f'{low}_staff_restroom', 466, (b['north_root'][0] + north_wall(block, X_ROOT)) / 2, 1, None)


# ---------------------------------------------------------------------------
# Floor 1: main corridor and the east side
# ---------------------------------------------------------------------------

def spine_nodes(L, floor, x, ys):
    keys = [L.node(f'f{floor}_spine_{round(y)}', x, y, floor) for y in sorted(ys)]
    L.chain(keys)
    return {round(y): k for y, k in zip(sorted(ys), keys)}


def build_floor1_east(L):
    f = 1
    plate = lambda pts: L.shape(f, 'plate', pts)
    plate(rect(498, 0, 545, 1250))
    plate(rect(498, 0, 600, 140))
    plate(H_WING)
    plate(rect(498, 138, 640, 234))
    plate([(498, 232), (640, 226), (725, 345), (772, 382), (772, 432), (740, 472), (498, 472)])
    plate([(498, 470), *FACADE, (498, 1245)])
    L.shape(f, 'room', H_WING, label='Block H east wing')
    L.shape(f, 'circle_room', [(640, 42)], r=13)
    L.shape(f, 'room', rect(555, 145, 597, 230))
    L.shape(f, 'room', rect(597, 145, 640, 230))
    L.shape(f, 'feature', G_HALL, fill='#c96b5c', label='Mini Red Hall')
    L.shape(f, 'feature', [(545, 412), (563, 394), (592, 423), (621, 394), (639, 412), (592, 459)], fill='#c8b06a')
    L.shape(f, 'feature', rect(545, 455, 588, 470), fill='#cdbb7a')
    L.shape(f, 'feature', CANTEEN, fill='#62c3c1')
    L.shape(f, 'room', rect(590, 560, 655, 618))
    L.shape(f, 'feature', rect(545, 669, 640, 683), fill='#1d8c93')
    L.shape(f, 'feature', rect(545, 688, 652, 782), fill='#9ed8d6')
    L.shape(f, 'room', rect(625, 815, 664, 860))
    L.shape(f, 'room', rect(627, 860, 664, 905))
    L.shape(f, 'room', rect(640, 1050, 676, 1088))
    L.shape(f, 'room', rect(642, 1088, 680, 1125))
    for i, (x, y, r) in enumerate(BOCHKAS, 1):
        L.shape(f, 'bochka', [(x, y)], r=r, label=f'Bochka {i}')
    L.shape(f, 'spiral', [SPIRAL[:2]], r=SPIRAL[2])
    L.shape(f, 'exit', [(772, 405)])

    s = spine_nodes(L, f, 520, [12, 72, 145, 210, 257, 300, 330, 412, 440, 464, 520, 600, 676, 730, 735,
                                835, 897, 975, 985, 1090, 1188, 1205, 1250]
                    + [corridor_route_y(b, 1) for b in BLOCKS])
    for block in BLOCKS:
        L.edge(s[round(corridor_route_y(block, 1))], f'f1_{block.lower()}_root')
    # Medical point sits in the spine column between H and G.
    L.shape(f, 'feature', rect(COLUMN[0] + 2, 222, COLUMN[1] - 2, 262), fill='#d38fbd')
    L.place('medical_point', 473, 242, f, s[257])
    # Block G hall, the secondary entrance and the table tennis zone.
    g1 = L.node('f1_g_passage', 568, 338, f)
    g2 = L.node('f1_g_passage_2', 650, 412, f)
    g3 = L.node('f1_g_vestibule', 735, 400, f)
    L.chain([s[300], g1, g2, g3])
    L.place('mini_red_hall', 645, 318, f, g1)
    L.place('entrance_g', 760, 405, f, g3)
    tennis = L.node('f1_tennis', 560, 412, f)
    L.edge(s[412], tennis)
    L.place('table_tennis_zone', 592, 428, f, tennis)
    lane = L.node('f1_print', 565, 448, f)
    s6 = L.node('f1_stair_06', 627, 448, f)
    L.chain([s[440], lane, s6])
    L.place('print_shop', 566, 463, f, lane)
    canteen = L.node('f1_canteen', 562, 560, f)
    L.edge(s[600], canteen)
    L.place('main_canteen', 640, 520, f, canteen)
    food = L.node('f1_food_point', 560, 676, f)
    L.edge(s[676], food)
    L.place('canteen_shop', 592, 676, f, food)
    red = L.node('f1_red_canteen', 560, 735, f)
    L.edge(s[735], red)
    L.place('red_canteen', 600, 735, f, red)
    for i, ((x, y, r), door) in enumerate(zip(BOCHKAS, [835, 975, 1090, 1188]), 1):
        n = L.node(f'f1_bochka_{i}', x - r - 6, y if i != 2 else 975, f)
        L.edge(s[door], n)
        L.place(f'bochka_{i}', x, y, f, n)
    spiral = L.node('f1_spiral', SPIRAL[0] - SPIRAL[2] - 4, SPIRAL[1], f)
    L.edge(s[897], spiral)
    L.place('stair_spiral_bochkas', SPIRAL[0], SPIRAL[1], f, spiral)
    L.spine1 = s


# ---------------------------------------------------------------------------
# Floor 2: narrow gallery corridor; the main hall below is open
# ---------------------------------------------------------------------------

def build_floor2_east(L):
    f = 2
    plate = lambda pts: L.shape(f, 'plate', pts)
    plate(rect(498, 0, 516, 1250))
    plate(rect(498, 62, 600, 92))
    plate(H_WING)
    plate([(498, 232), (518, 232), (668, 392), (650, 410), (498, 248)])
    plate(rect(516, 505, 560, 535))
    plate([(556, 432), (742, 432), (742, 540), (700, 600), (700, 620), (556, 620)])
    plate(rect(516, 790, 565, 1245))
    L.shape(f, 'void', rect(516, 140, 555, 230), under=True)
    L.shape(f, 'void', rect(516, 250, 545, 500), under=True)
    L.shape(f, 'void', rect(516, 540, 545, 785), label='Open to floor 1', under=True)
    L.shape(f, 'room', H_WING, label='Block H east wing')
    L.shape(f, 'circle_room', [(640, 42)], r=13)
    L.shape(f, 'room', rect(560, 145, 640, 250))
    L.shape(f, 'room', G_HALL, label='Block G hall, upper level')
    L.shape(f, 'feature', [(556, 432), (742, 432), (742, 540), (700, 600), (700, 620), (556, 620)],
            fill='#b7e2e0', label='Canteen hall')
    L.shape(f, 'room', rect(595, 535, 655, 580))
    L.shape(f, 'room', rect(625, 815, 664, 860))
    L.shape(f, 'room', rect(627, 860, 664, 905))
    L.shape(f, 'room', rect(640, 1050, 676, 1088))
    L.shape(f, 'room', rect(642, 1088, 680, 1125))
    for i, (x, y, r) in enumerate(BOCHKAS, 1):
        L.shape(f, 'bochka_upper', [(x, y)], r=r)
    L.shape(f, 'spiral', [SPIRAL[:2]], r=SPIRAL[2])

    s = spine_nodes(L, f, 507, [12, 77, 210, 240, 257, 464, 520, 730, 835, 897, 975, 985, 1090, 1188, 1205, 1250]
                    + [corridor_route_y(b, 2) for b in BLOCKS])
    for block in BLOCKS:
        L.edge(s[round(corridor_route_y(block, 2))], f'f2_{block.lower()}_root')
    walk = L.node('f2_g_walkway', 600, 330, f)
    L.edge(s[240], walk)
    hall = L.node('f2_canteen_hall', 575, 520, f)
    core = L.node('f2_canteen_stairs', 605, 560, f)
    L.chain([s[520], hall, core])
    for i, ((x, y, r), door) in enumerate(zip(BOCHKAS, [835, 975, 1090, 1188]), 1):
        n = L.node(f'f2_bochka_{i}', x - r - 6 if i in (1, 3) else 560, y if i != 2 else 975, f)
        L.edge(s[door], n)
        L.place(f'bochka_{i}_floor_2', x, y, f, n,
                name=f'Bochka {i} upper level', category='Study', block='Campus spine', floors=[2],
                notes='Upper seating level of the Bochka on the floor-2 evacuation plan. Doors and use are not confirmed.')
    spiral = L.node('f2_spiral', SPIRAL[0] - SPIRAL[2] - 4, SPIRAL[1], f)
    L.edge(s[897], spiral)
    L.spine2 = s


# ---------------------------------------------------------------------------
# Floor 3: corridor along the blocks, bridges to the canteen and the Bochkas
# ---------------------------------------------------------------------------

def build_floor3_east(L):
    f = 3
    plate = lambda pts: L.shape(f, 'plate', pts)
    plate(rect(498, 0, 508, 1250))
    plate(rect(506, 517, 545, 533))
    plate([(540, 430), (715, 430), (715, 690), (540, 690)])
    plate(rect(506, 826, 545, 840))
    plate(rect(506, 1094, 545, 1108))
    L.shape(f, 'void', rect(508, 140, 540, 1240), label='Open to below', under=True)
    L.shape(f, 'room', [(545, 20), (695, 20), (700, 70), (640, 150), (560, 140)], label='Block H east wing')
    L.shape(f, 'circle_room', [(615, 78)], r=16)
    L.shape(f, 'room', rect(535, 165, 620, 250))
    L.shape(f, 'room', G_HALL, label='Block G hall, top level')
    L.shape(f, 'feature', [(540, 430), (715, 430), (715, 690), (540, 690)], fill='#62c3c1')
    L.shape(f, 'room', rect(600, 640, 690, 688))
    L.shape(f, 'room', rect(632, 720, 680, 830))
    for i, (x, y, r) in enumerate(BOCHKAS, 1):
        L.shape(f, 'bochka_top', [(x, y)], r=r - 3)
    # Bridge between the Bochkas (Y-shaped from the main corridor).
    L.shape(f, 'bridge', [(590, 1062), (610, 1028)], w=12)
    L.shape(f, 'bridge', [(590, 1118), (608, 1145)], w=12)

    s = spine_nodes(L, f, 503, [12, 525, 832, 1100, 1250] + [corridor_route_y(b, 3) for b in BLOCKS])
    for block in BLOCKS:
        L.edge(s[round(corridor_route_y(block, 3))], f'f3_{block.lower()}_root')
    canteen = L.node('f3_canteen', 600, 560, f)
    L.chain([s[525], L.node('f3_canteen_bridge', 548, 525, f), canteen])
    L.place('canteen_floor_3', 665, 540, f, canteen)
    s6 = L.node('f3_stair_06', 627, 455, f)
    L.edge(canteen, s6)
    core = L.node('f3_canteen_stairs', 592, 600, f)
    L.edge(canteen, core)
    b1 = L.node('f3_bochka_1', 541, 832, f)
    L.edge(s[832], b1)
    hub = L.node('f3_bochka_3', 545, 1100, f)
    L.edge(s[1100], hub)
    b2 = L.node('f3_bochka_2', 606, 1032, f)
    b4 = L.node('f3_bochka_4', 606, 1141, f)
    L.edge(hub, b2)
    L.edge(hub, b4)
    for i, (n, (x, y, r)) in enumerate(zip([b1, b2, hub, b4], BOCHKAS), 1):
        L.place(f'bochka_{i}_floor_3', x, y, f, n,
                name=f'Bochka {i} top level', category='Study', block='Campus spine', floors=[3],
                notes='Round space above the Bochka, reached by a bridge on the floor-3 evacuation plan. Use is not confirmed.')
    L.spine3 = s


# ---------------------------------------------------------------------------
# Blocks A, B and C (south end)
# ---------------------------------------------------------------------------

def build_south(L):
    for f in (1, 2, 3):
        plate = lambda pts: L.shape(f, 'plate', pts)
        plate(C_HALL)
        plate([(498, 1240), (545, 1240), (545, 1300), (498, 1300)])
        if f == 1:
            plate([(245, 1318), (300, 1318), (300, 1338), (455, 1338), (480, 1380), (500, 1398), (500, 1485),
                   (478, 1465), (345, 1478), (345, 1530), (245, 1530)])
            plate(rect(108, 1316, 248, 1528))
            plate([(213, 1585), (222, 1597), (330, 1528), (322, 1515)])
            L.shape(f, 'feature', WIFI, fill='#5d63b8', rings=True)
            L.shape(f, 'feature', [(655, 1290), (680, 1265), (742, 1330), (717, 1355)], fill='#78b59a', label='Cloakroom')
            L.shape(f, 'feature', rect(115, 1348, 240, 1500), fill='#c45d4d', label='Red Hall', seats=True)
            L.shape(f, 'room', rect(135, 1318, 200, 1346))
            L.shape(f, 'room', rect(115, 1502, 245, 1526))
            L.shape(f, 'feature', LIBRARY, fill='#1d8c93')
            L.shape(f, 'room', rect(300, 1340, 340, 1380))
            L.shape(f, 'room', rect(340, 1340, 395, 1380))
            L.shape(f, 'room', rect(395, 1340, 448, 1380))
            L.shape(f, 'room', rect(315, 1388, 440, 1404))
            L.shape(f, 'room', rect(248, 1486, 296, 1528))
            L.shape(f, 'exit', [(733, 1424)])
        elif f == 2:
            plate([(245, 1340), (450, 1340), (500, 1398), (500, 1585), (245, 1585)])
            L.shape(f, 'void', WIFI, label='Open to WiFi Zone', rings=True)
            L.shape(f, 'room', [(655, 1290), (680, 1265), (742, 1330), (717, 1355)])
            L.shape(f, 'void', rect(108, 1325, 248, 1545), label='Red Hall below')
            L.shape(f, 'room', rect(130, 1320, 220, 1348))
            L.shape(f, 'room', rect(115, 1515, 240, 1545))
            L.shape(f, 'feature', rect(250, 1400, 445, 1500), fill='#8fcbd0')
            L.shape(f, 'room', rect(310, 1345, 445, 1392))
            L.shape(f, 'room', rect(345, 1392, 445, 1428))
        else:
            plate([(245, 1345), (450, 1345), (482, 1400), (482, 1580), (245, 1580)])
            L.shape(f, 'void', WIFI, label='Open to below', rings=False)
            L.shape(f, 'room', [(612, 1300), (640, 1275), (738, 1365), (690, 1440), (640, 1440)])
            L.shape(f, 'room', rect(310, 1350, 440, 1408))
            L.shape(f, 'void', rect(108, 1330, 240, 1520), label='Block A (no floor 3)', outline_only=True)
        L.shape(f, 'stairs', rect(300, 1496, 322, 1518))
        L.shape(f, 'stairs', [(652, 1300), (664, 1288), (684, 1308), (672, 1320)])
        L.shape(f, 'column', [(COLUMN[0], 1240), (COLUMN[1], 1240), (COLUMN[1], 1366), (482, 1380), (COLUMN[0], 1380)])

    s = L.spine1
    hub = L.node('f1_c_hub', 545, 1290, 1)
    east = L.node('f1_c_east', 640, 1300, 1)
    wing = L.node('f1_c_wing', 690, 1365, 1)
    door = L.node('f1_c_entrance', 718, 1410, 1)
    L.chain([s[1250], hub, east, wing, door])
    L.place('wifi_zone', 562, 1397, 1, hub)
    L.place('cloakroom', 698, 1310, 1, wing)
    L.place('entrance_c_main', 735, 1424, 1, door)
    link = L.node('f1_bc_link', 478, 1398, 1)
    b_hub = L.node('f1_b_hub', 420, 1440, 1)
    b_west = L.node('f1_b_west', 250, 1440, 1)
    L.chain([hub, link, b_hub])
    L.place('red_hall', 178, 1424, 1, b_west)
    lib = L.node('f1_library', 420, 1470, 1)
    L.edge(b_hub, lib)
    L.place('library', 420, 1515, 1, lib)
    rest = L.node('f1_b_restroom', 320, 1440, 1)
    L.place('restroom_lower_central', 320, 1360, 1, rest)
    b_stair = L.node('f1_b_stair', 311, 1470, 1)
    L.chain([b_hub, rest, b_west])
    L.edge(rest, b_stair)
    c_stair = L.node('f1_c_stair', 660, 1312, 1)
    L.edge(east, c_stair)
    # Floor 2: gallery round the atrium and the library's upper floor.
    s = L.spine2
    hub2 = L.node('f2_c_hub', 545, 1290, 2)
    east2 = L.node('f2_c_east', 640, 1300, 2)
    L.chain([s[1250], hub2, east2])
    c2 = L.node('f2_c_stair', 660, 1312, 2)
    L.edge(east2, c2)
    link2 = L.node('f2_bc_link', 478, 1398, 2)
    b2 = L.node('f2_b_hub', 420, 1440, 2)
    lib2 = L.node('f2_library', 350, 1450, 2)
    st2 = L.node('f2_b_stair', 311, 1480, 2)
    L.chain([hub2, link2, b2, lib2, st2])
    L.place('library_floor_2', 340, 1460, 2, lib2,
            name='Library · Floor 2', category='Study', block='Block B', floors=[2],
            notes='Upper library floor (open hall with columns) on the floor-2 evacuation plan; exact extent unconfirmed.')
    # Floor 3: hall above Block B and the rooms in the Block C wing.
    s = L.spine3
    hub3 = L.node('f3_c_hub', 545, 1290, 3)
    east3 = L.node('f3_c_east', 640, 1300, 3)
    L.chain([s[1250], hub3, east3])
    c3 = L.node('f3_c_stair', 660, 1312, 3)
    L.edge(east3, c3)
    link3 = L.node('f3_bc_link', 470, 1398, 3)
    b3 = L.node('f3_b_hub', 400, 1450, 3)
    st3 = L.node('f3_b_stair', 311, 1480, 3)
    L.chain([hub3, link3, b3, st3])


# ---------------------------------------------------------------------------
# Stairs and lifts
# ---------------------------------------------------------------------------

def build_vertical(L):
    def landing(key, x, y, floor, node, name=None, base=None, floors=None, **extra):
        record = {'name': name, 'category': 'Stairs', 'floors': floors} if name else {}
        record.update(extra)
        if base:
            record['base'] = base
        L.place(key, x, y, floor, node, **record)

    def stair_series(label, keys, nodes):
        for a, b in zip(nodes, nodes[1:]):
            L.edge(a, b, 'stairs', label)

    # Block end staircases and corridor lifts (every block, floors 1-3).
    for block in BLOCKS:
        low = block.lower()
        x = (X_END + X_ROOMS) / 2
        y = (north_top(block, x) + north_wall(block, x)) / 2
        name = f'Block {block} end staircase'
        stair_series(name, None, [f'f{f}_{low}_end' for f in (1, 2, 3)])
        landing(f'stair_block_{low}', x, y, 1, f'f1_{low}_end')
        for f in (2, 3):
            landing(f'stair_block_{low}_floor_{f}', x, y, f, f'f{f}_{low}_end', name=f'{name} · Floor {f}',
                    base=f'stair_block_{low}', block=f'Block {block}', floors=[-1, 1, 2, 3])
        if block in 'DFH':
            for a, b in ((1, 2), (2, 3)):
                L.edge(f'f{a}_{low}_lift', f'f{b}_{low}_lift', 'lift', f'Block {block} lift')
            ly = north_wall(block, 355) + 5
            L.place(f'lift_block_{low}', 355, ly, 1, f'f1_{low}_lift')
            for f in (2, 3):
                L.place(f'lift_block_{low}_floor_{f}', 355, ly, f, f'f{f}_{low}_lift',
                        name=f'Block {block} lift · Floor {f}', category='Lift', block=f'Block {block}',
                        floors=[-1, 1, 2, 3], base=f'lift_block_{low}')
    # Numbered main-corridor staircases, matched to the user's location descriptions.
    numbered = {
        '08': (548, 257, 257, 257, 'Above G, beside Mini Red Hall'),
        '05': (430, CURVED_STAIRS['FE'], 730, 730, 'Between E and F, beside Red Canteen'),
        '04': (430, CURVED_STAIRS['ED'], 985, 985, 'Opposite the second Bochka from the top'),
        '03': (510, 1205, 1205, 1205, 'Below D general restroom, left of the bottommost Bochka'),
    }
    for number, (x, y, s1, s2, _) in numbered.items():
        lower = L.node(f'f1_stair_{number}', x, y, 1)
        upper = L.node(f'f2_stair_{number}', x, y, 2)
        L.edge(L.spine1[s1], lower)
        L.edge(L.spine2[s2], upper)
        L.edge(lower, upper, 'stairs', f'Staircase {int(number)}')
        landing(f'stair_main_{number}', x, y, 1, lower)
        landing(f'stair_main_{number}_floor_2', x, y, 2, upper, name=f'Staircase {int(number)} · Floor 2',
                base=f'stair_main_{number}', floors=[1, 2])
    for f in (1, 2):
        L.shape(f, 'stairs', rect(538, 245, 560, 270))
        L.shape(f, 'stairs', rect(503, 1192, 518, 1220))
    # Unnumbered curved stairs between H/G and G/F.
    for gap, name in (('HG', 'Curved staircase between Blocks H and G'), ('GF', 'Curved staircase between Blocks G and F')):
        y = CURVED_STAIRS[gap]
        key = f'stair_curved_{gap.lower()}'
        lower, upper = L.node(f'f1_{key}', 430, y, 1), L.node(f'f2_{key}', 430, y, 2)
        L.edge(L.spine1[y], lower)
        L.edge(L.spine2[y], upper)
        L.edge(lower, upper, 'stairs', name)
        note = 'Curved staircase drawn on the floor-1 and floor-2 evacuation plans; landings are approximate.'
        landing(key, 430, y, 1, lower, name=name, floors=[1, 2], notes=note)
        landing(f'{key}_floor_2', 430, y, 2, upper, name=f'{name} · Floor 2', floors=[1, 2], notes=note)
    # Spiral stairs by the Bochkas.
    L.edge('f1_spiral', 'f2_spiral', 'stairs', 'Bochka spiral stairs')
    landing('stair_spiral_floor_2', SPIRAL[0], SPIRAL[1], 2, 'f2_spiral', name='Spiral stairs · Floor 2',
            base='stair_spiral_bochkas', floors=[-1, 1, 2])
    # Staircase 6 runs from below the table tennis zone straight to the floor-3 canteen.
    for f in (1, 2, 3):
        L.shape(f, 'stairs', rect(612, 451, 642, 470))
    L.edge('f1_stair_06', 'f3_stair_06', 'stairs', 'Staircase 6 (no floor-2 stop)')
    landing('stair_main_06', 627, 461, 1, 'f1_stair_06')
    landing('stair_main_06_floor_3', 627, 461, 3, 'f3_stair_06', name='Staircase 6 · Floor 3',
            base='stair_main_06', floors=[1, 3], skips_floors=[2])
    # Canteen stairs: floor 2 hall to the floor-3 canteen.
    for f in (2, 3):
        L.shape(f, 'stairs', rect(598, 590, 620, 612) if f == 3 else rect(600, 545, 622, 575))
    L.edge('f2_canteen_stairs', 'f3_canteen_stairs', 'stairs', 'Canteen stairs')
    landing('stair_canteen_23', 611, 560, 2, 'f2_canteen_stairs', name='Canteen stairs · Floors 2–3', floors=[2, 3],
            notes='Staircase in the canteen core on the floor-2 and floor-3 evacuation plans; landings approximate.')
    landing('stair_canteen_23_floor_3', 609, 601, 3, 'f3_canteen_stairs', name='Canteen stairs · Floor 3',
            base='stair_canteen_23', floors=[2, 3])
    # Staircases in Blocks B and C that appear at the same place on floors 1-3.
    for key, name, x, y, nodes in (('stair_block_c', 'Block C staircase', 668, 1304, ['f1_c_stair', 'f2_c_stair', 'f3_c_stair']),
                                   ('stair_block_b', 'Block B staircase', 311, 1507, ['f1_b_stair', 'f2_b_stair', 'f3_b_stair'])):
        stair_series(name, None, nodes)
        note = 'Staircase drawn at the same place on the floor 1-3 evacuation plans; landings are approximate.'
        landing(key, x, y, 1, nodes[0], name=name, floors=[1, 2, 3], block=name.rsplit(' ', 1)[0], notes=note)
        for f in (2, 3):
            landing(f'{key}_floor_{f}', x, y, f, nodes[f - 1], name=f'{name} · Floor {f}', floors=[1, 2, 3],
                    block=name.rsplit(' ', 1)[0], notes=note)


def build_labels(L):
    for block in BLOCKS:
        b = band(block)
        y = (b['north_root'][0] + b['south'][1]) / 2
        color = BLOCK_COLORS[block]
        L.label(f'Block {block}', 250, y - 6, size=17, bold=True, color=color, align='end')
        for i, line in enumerate(FACULTIES[block]):
            L.label(line, 250, y + 13 + i * 14, size=11.5, color=color, align='end')
    for text, x, y, floors in (('Block A', 178, 1306, (1, 2)), ('Block B', 300, 1620, (1, 2, 3)),
                               ('Block C', 700, 1478, (1, 2, 3))):
        L.label(text, x, y, floors, size=13, bold=True, color='#4b5d78', align='middle')


def shift(L):
    """Move the trace frame into the map frame (top margin)."""
    move = lambda p: (round(p[0], 2), round(p[1] + DY, 2))
    for floor, shapes in L.shapes.items():
        for s in shapes:
            s['points'] = [move(p) for p in s['points']]
    for label in L.labels:
        label['y'] = round(label['y'] + DY, 2)
    for key, (x, y) in L.nodes.items():
        L.nodes[key] = [x, round(y + DY, 2)]
    for p in L.places.values():
        p['x'], p['y'] = round(p['x'], 2), round(p['y'] + DY, 2)
        if p['geometry']:
            p['geometry']['y'] = round(p['geometry']['y'] + DY, 2)
    return L
