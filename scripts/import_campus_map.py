"""Compile the supplied map exchange bundle into app assets.

Run: python3 scripts/import_campus_map.py /path/to/sdu-map
Requires PyYAML in the importing environment only, not in the running API.
"""
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zlib

import yaml
from compile_upper_floor import compile_floors

ROOT = Path(__file__).resolve().parents[1]
bundle = Path(sys.argv[1])
data = yaml.safe_load((bundle / 'campus.yaml').read_text())
tree = ET.parse(bundle / 'floor-1.svg')
ns = '{http://www.w3.org/2000/svg}'
# Let the Flutter scaffold supply its theme background instead of a white box.
for element in list(tree.getroot()):
    if (element.tag == ns + 'rect' and element.get('width') == '765'
            and element.get('height') == '1280' and element.get('fill') == 'white'):
        tree.getroot().remove(element)
elements = {e.get('id'): e for e in tree.iter() if e.get('id')}
categories = {
    'event_hall': 'Hall', 'restroom': 'Restroom', 'lounge': 'Study',
    'cloakroom': 'Service', 'entrance': 'Entrance', 'library': 'Study',
    'canteen': 'Food', 'food_shop': 'Food', 'dining_area': 'Food',
    'medical': 'Health', 'recreation': 'Recreation', 'shop': 'Printer',
    'classroom': 'Classroom', 'innovation_center': 'Service',
    'lecture_hall_structure': 'Hall', 'stairs': 'Stairs',
    'spiral_stairs': 'Stairs', 'elevator': 'Lift',
}
legacy = {'entrance_c_main': 1, 'library': 2, 'main_canteen': 3,
          'medical_point': 6, 'print_shop': 7}
places = []
for record in data['places'] + data['structures'] + data['vertical_infrastructure']:
    record = dict(record)
    key = record['id']
    anchor = record.get('anchor')
    if not anchor and record['type'] == 'lecture_hall_structure':
        shape = elements[record['svg_id']]
        shift = re.search(r'translate\(([-\d.]+)', shape.get('transform', ''))
        anchor = {'x': float(shape.get('cx')) + (float(shift[1]) if shift else 0),
                  'y': float(shape.get('cy')), 'floor': 1}
    positioned = bool(anchor) and 'illustrative' not in record.get('position_status', '')
    floor = record.get('floor', record.get('documented_floor', (anchor or {}).get('floor', 1)))
    floors = record.get('floors', record.get('connects_floors', [floor] if floor is not None else []))
    notes = [record.get('notes', ''), record.get('location_description', ''), record.get('numbering', '')]
    if record.get('parent_place') == 'library':
        notes.append('Inside the library; exact position and step-free approach are not confirmed.')
    if record.get('lecture_hall_count'):
        notes.append('Contains two lecture halls and an upper study space; internal entrances and upper floor are unconfirmed.')
    name = record.get('name', 'Library lift' if key == 'library_lift' else
                      'Library staircase' if key == 'library_stairs' else
                      f"Block {record.get('block', '')} end staircase")
    places.append({
        'id': legacy.get(key, 1000 + zlib.crc32(key.encode()) % 100000000),
        'map_key': key, 'name': name, 'category': categories[record['type']],
        'block': 'Block ' + record['block'] if record.get('block') else 'Campus spine',
        'floor': 'Floor ' + str(floor) if floor is not None else 'Floor unknown',
        'map_floor': floor, 'floors': floors, 'has_position': positioned,
        'x': anchor['x'] / 765 if positioned else 0,
        'y': anchor['y'] / 1280 if positioned else 0,
        'geometry': record.get('geometry'), 'access': record.get('access', 'public'),
        'notes': ' '.join(n for n in notes if n),
        'position_status': record.get('position_status', 'Approximate schematic marker' if positioned else 'Not positioned'),
        'opening_hours': 'Not confirmed', 'contact': 'Not confirmed',
        'accessible': False, 'accessibility_status': 'Not verified',
        'aliases': ','.join(record.get('aliases', []) + record.get('services', []) + [key.replace('_', ' ')]),
        'access_via': record.get('access_via', []),
        'skips_floors': record.get('skips_floors', []),
        'entrances_from_floors': record.get('entrances_from_floors', []),
    })
assert len({p['id'] for p in places}) == len(places)
# Keep fixed shapes and block/faculty labels; rooms and infrastructure are drawn by Flutter.
remove_groups = {'block-D-lower', 'confirmed-vertical-infrastructure', 'main-corridor-stairs', 'stair-block-d', 'entrances'}
keep_labels = ('label-block-', 'label-faculty-', 'label-A', 'label-B', 'label-C')
labels = []
for parent in list(tree.iter()):
    for element in list(parent):
        eid = element.get('id', '')
        if eid in remove_groups or (element.tag == ns + 'text' and not eid.startswith(keep_labels)):
            parent.remove(element)
        elif element.tag == ns + 'text':
            shift = re.search(r'translate\(([-\d.]+)', element.get('transform', ''))
            labels.append({'text': element.text, 'x': float(element.get('x')) + (float(shift[1]) if shift else 0),
                           'y': float(element.get('y')), 'color': element.get('fill'),
                           'size': float(element.get('font-size')), 'align': element.get('text-anchor'),
                           'bold': eid.startswith('label-block-')})
            parent.remove(element)
# Inline CSS properties for predictable flutter_svg rendering.
for element in tree.iter():
    cls = element.pop('class', '') if hasattr(element, 'pop') else element.attrib.pop('class', '')
    if cls == 'outline':
        element.set('stroke', '#888888'); element.set('stroke-width', '1')
    if cls == 'division':
        element.set('stroke', '#555555'); element.set('stroke-opacity', '.32')
    if element.tag == ns + 'text':
        element.set('font-family', 'Arial')
        if cls == 'block-label': element.set('font-weight', 'bold')
for parent in tree.iter():
    for element in list(parent):
        if element.tag == ns + 'style': parent.remove(element)
ET.register_namespace('', ns[1:-1])
asset = ROOT / 'assets/maps'
asset.mkdir(parents=True, exist_ok=True)
tree.write(asset / 'floor-1-background.svg', encoding='unicode')
route_file = bundle / 'routing-draft.yaml'
routing = yaml.safe_load(route_file.read_text()) if route_file.exists() else {'status': 'not_surveyed', 'nodes': {}, 'edges': [], 'attachments': {}}
routing = compile_floors(places, routing, asset)
assert all(e['a'] in routing['nodes'] and e['b'] in routing['nodes'] for e in routing['edges'])
assert all(key in {p['map_key'] for p in places} and node in routing['nodes'] for key, node in routing['attachments'].items())
payload = {'version': 2, 'width': 765, 'height': 1280, 'mapped_floors': [1,2], 'labels': labels,
           'routing_status': routing['status'], 'routing': routing, 'places': places}
encoded = json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
(asset / 'campus.json').write_text(encoded)
api_data = ROOT / 'backend/app/data'
api_data.mkdir(parents=True, exist_ok=True)
(api_data / 'campus.json').write_text(encoded)
print(f'Imported {len(places)} records; {sum(p["has_position"] for p in places)} positioned across floors 1 and 2.')
