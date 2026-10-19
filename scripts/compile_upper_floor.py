"""Compile the user's floor-2 sketch and explicitly requested assumed room pattern."""
import copy
import xml.etree.ElementTree as ET
import zlib


def compile_floors(places, graph, asset):
    ns = '{http://www.w3.org/2000/svg}'
    graph = copy.deepcopy(graph)
    graph['attachments'].pop('stair_main_01', None)
    places[:] = [p for p in places if p['map_key'] != 'stair_main_01']
    graph['node_floors'] = {key: 1 for key in graph['nodes']}
    graph['edges'] = [{'a': a, 'b': b, 'kind': 'corridor'} for a, b in graph['edges']]
    nodes, edges, attach = graph['nodes'], graph['edges'], graph['attachments']
    def node(key, x, y, floor):
        nodes[key] = [x, y]
        graph['node_floors'][key] = floor
        return key
    def edge(a, b, kind='corridor', label=''):
        edges.append({'a': a, 'b': b, 'kind': kind, 'label': label})
    def place(key, name, category, x, y, floor, connection, base=None, **extra):
        record = copy.deepcopy(base or places[0])
        record.update(id=1000 + zlib.crc32(key.encode()) % 100000000,
                      map_key=key, name=name, category=category, block='Campus spine',
                      map_floor=floor, floor=f'Floor {floor}', floors=[floor],
                      x=x/765, y=y/1280, has_position=True, geometry=None, access='public',
                      aliases=name.lower(), notes='Position traced from the user sketch; exact door or landing unverified.',
                      skips_floors=[], entrances_from_floors=[])
        record.update(extra)
        places.append(record)
        attach[key] = connection
        return record
    # Red main walkway from the user's sketch; all marked platforms are connected.
    previous = None
    for y in [95, 135, 250, 318, 501, 610, 685, 720, 763, 845, 900, 1035, 1125]:
        key = node(f'f2_spine_{y}', 384, y, 2)
        if previous: edge(previous, key)
        previous = key
    # Branches reproduce the user's red outlines; geometry is still schematic.
    bands = {'D': (866, 878), 'E': (685, 695), 'F': (501, 514), 'G': (318, 331), 'H': (139, 148)}
    rooms = []
    for block, (cy, ry) in bands.items():
        for floor in [1, 2]:
            spine = {'D': 'spine_d', 'E': 'spine_e', 'F': 'spine_f', 'G': 'spine_g', 'H': 'spine_h'}[block] if floor == 1 else f'f2_spine_{135 if block == "H" else 900 if block == "D" else cy}'
            last = spine
            for number in range(1, 5):
                x = 384 - (number - .5)*38.25
                key = f'{block.lower()}{floor}0{number}'
                corridor = node(f'room_approach_{key}', x, cy, floor)
                edge(last, corridor)
                last = corridor
                existing = next((p for p in places if p['map_key'] == key), None)
                if existing:
                    attach[key] = corridor
                    record = existing
                else:
                    record = place(key, key.upper(), 'Classroom', x, ry+19.5, floor, corridor,
                        notes='Assumed four-room pattern requested by the user, not individually verified. Door positions and equal room widths are schematic.')
                record['block'] = f'Block {block}'
                record['geometry'] = {'x': x-19.125, 'y': ry, 'width': 38.25, 'height': 39}
                rooms.append(record)
            lift = next((p for p in places if p['map_key'] == f'lift_block_{block.lower()}'), None)
            if lift:
                landing = node(f'f{floor}_lift_{block.lower()}', 295, cy, floor)
                edge(f'room_approach_{block.lower()}{floor}02', landing)
                if floor == 1: attach[lift['map_key']] = landing
                else:
                    place(f'lift_block_{block.lower()}_floor_2', f'Block {block} lift · Floor 2', 'Lift', 295, cy, 2, landing, base=lift,
                          block=f'Block {block}', floors=[-1,1,2,3])
                    edge(f'f1_lift_{block.lower()}', landing, 'lift', f'Block {block} lift')
    stairs = {'03': (457,920,900), '04': (498,763,763), '05': (457,611,610), '08': (466,250,250)}
    block_stair = next(p for p in places if p['map_key'] == 'stair_block_d')
    low_d = node('f1_stair_block_d',216,849,1)
    high_d = node('f2_stair_block_d',216,849,2)
    edge('room_approach_d104',low_d)
    edge('room_approach_d204',high_d)
    edge(low_d,high_d,'stairs','Block D end staircase')
    attach[block_stair['map_key']] = low_d
    place('stair_block_d_floor_2','Block D end staircase · Floor 2','Stairs',216,849,2,high_d,
          base=block_stair,block='Block D',floors=[-1,1,2,3])
    for number, (x,y,sy) in stairs.items():
        original = next(p for p in places if p['map_key'] == f'stair_main_{number}')
        lower = node(f'f1_stair_{number}', original['x']*765, original['y']*1280, 1)
        edge(attach[original['map_key']], lower)
        attach[original['map_key']] = lower
        upper = node(f'f2_stair_{number}', x, y, 2)
        edge(f'f2_spine_{sy}', upper)
        edge(lower, upper, 'stairs', f'Staircase {int(number)}')
        place(f'stair_main_{number}_floor_2', f'Staircase {int(number)} · Floor 2', 'Stairs', x,y,2,upper,base=original, floors=original['floors'])
    # Continuous platform branches drawn around the Bochkas.
    platform = node('f2_platform', 510,720,2)
    edge('f2_spine_720', platform)
    for i, (x,y) in enumerate([(521,677),(550,775),(521,846),(550,910)], 1):
        n = node(f'f2_bochka_{i}',x,y,2)
        edge(platform,n)
        platform = n
        place(f'bochka_{i}_floor_2',f'Bochka {i} upper platform','Study',x,y,2,n)
    edge(platform,'f2_spine_900')
    spiral = next(p for p in places if p['map_key']=='stair_spiral_bochkas')
    low = node('f1_spiral',541,720,1)
    edge('spine_e',low)
    high = node('f2_spiral',541,720,2)
    edge('f2_platform',high)
    edge(low,high,'stairs','Bochka spiral stairs')
    attach[spiral['map_key']] = low
    place('stair_spiral_floor_2','Spiral stairs · Floor 2','Stairs',541,720,2,high,base=spiral, floors=[-1,1,2])
    library = node('f2_library',210,1160,2)
    edge('f2_spine_1125',library)
    place('library_floor_2','Library · Floor 2','Study',210,1160,2,library,block='Block B')
    # Floor 3 has only the confirmed canteen terminal, NOT an invented floor plan.
    canteen = node('f2_canteen_stairs',592,610,2)
    edge('f2_spine_610',canteen)
    place('stair_canteen_23','Canteen stairs · Floors 2–3','Stairs',592,610,2,canteen,floors=[2,3])
    top = node('f3_canteen',592,610,3)
    edge(canteen,top,'stairs','Canteen stairs')
    target = next(p for p in places if p['map_key']=='canteen_floor_3')
    attach[target['map_key']] = top
    s6 = next(p for p in places if p['map_key']=='stair_main_06')
    landing = node('f1_stair_06',541,385,1)
    edge('spine_400',landing)
    attach[s6['map_key']] = landing
    edge(landing,top,'stairs','Staircase 6 (no floor-2 stop)')
    # Muted building footprint is orientation context, not a claim of walkable floor-2 space.
    svg = ET.Element(ns+'svg',width='765',height='1280',viewBox='0 0 765 1280')
    base = ET.SubElement(svg,ns+'g',id='floor-2-building-context',opacity='.48')
    original = ET.parse(asset/'floor-1-background.svg').getroot()
    for child in original:
        if child.tag in [ns+'title',ns+'desc']: continue
        base.append(copy.deepcopy(child))
    for shape in base.iter():
        if shape.get('id') == 'corridor-main':
            shape.set('fill','#e0e4ed')
    walkways = ET.SubElement(svg,ns+'g',id='floor-2-walkways')
    # Outer edges make real upper-floor connections stand out from the ghosted footprint.
    for width, color in [(28,'#9aa8bd'), (23,'#d5dce8')]:
        for e in edges:
            if e['kind'] != 'corridor' or graph['node_floors'][e['a']] != 2: continue
            a,b = nodes[e['a']],nodes[e['b']]
            ET.SubElement(walkways,ns+'line',x1=str(a[0]),y1=str(a[1]),x2=str(b[0]),y2=str(b[1]),
                          stroke=color,**{'stroke-width':str(width),'stroke-linecap':'round'})
    for i,(x,y) in enumerate([(521,677),(550,775),(521,846),(550,910)],1):
        ET.SubElement(svg,ns+'ellipse',cx=str(x),cy=str(y),rx='34',ry='30',fill='#ecd89d',stroke='#b59b60')
    ET.SubElement(svg,ns+'rect',x='180',y='1140',width='145',height='65',rx='8',fill='#a5d5d5')
    ET.ElementTree(svg).write(asset/'floor-2-background.svg',encoding='unicode')
    return graph
