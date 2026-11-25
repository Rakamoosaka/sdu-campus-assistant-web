"""Build the app's campus map assets from the catalogue and the traced layout.

Run: python3 scripts/import_campus_map.py docs/map-source
Needs PyYAML in the importing environment only, not in the running API.

Inputs
- <bundle>/campus.yaml: catalogue facts (names, types, served floors, notes).
- scripts/campus_layout.py: geometry, walking graph and positions for floors 1-3,
  traced from the evacuation plans in <bundle>/evacuation-plans/.

Outputs
- assets/maps/floor-{1,2,3}-background.svg
- assets/maps/campus.json and backend/app/data/campus.json (identical)
"""
import json
import math
from pathlib import Path
import sys
import zlib
from xml.sax.saxutils import escape

import yaml

import campus_layout as layout

ROOT = Path(__file__).resolve().parents[1]
FLOORS = [1, 2, 3]
CATEGORIES = {
    'event_hall': 'Hall', 'restroom': 'Restroom', 'lounge': 'Study',
    'cloakroom': 'Service', 'entrance': 'Entrance', 'library': 'Study',
    'canteen': 'Food', 'food_shop': 'Food', 'dining_area': 'Food',
    'medical': 'Health', 'recreation': 'Recreation', 'shop': 'Printer',
    'classroom': 'Classroom', 'innovation_center': 'Service',
    'lecture_hall_structure': 'Hall', 'stairs': 'Stairs',
    'spiral_stairs': 'Stairs', 'elevator': 'Lift',
}
LEGACY_IDS = {'entrance_c_main': 1, 'library': 2, 'main_canteen': 3, 'medical_point': 6, 'print_shop': 7}
TRACED = 'Traced from the evacuation plans; approximate position'


def stable_id(key):
    return LEGACY_IDS.get(key, 1000 + zlib.crc32(key.encode()) % 100000000)


def catalogue_place(record, position):
    key = record['id']
    floor = record.get('floor', record.get('documented_floor', 1))
    floors = record.get('floors', record.get('connects_floors', [floor] if floor is not None else []))
    name = record.get('name') or {
        'library_lift': 'Library lift', 'library_stairs': 'Library staircase',
    }.get(key, f"Block {record.get('block', '')} end staircase")
    notes = [record.get('notes', ''), record.get('location_description', ''), record.get('numbering', '')]
    if record.get('lecture_hall_count'):
        notes.append('Contains two lecture halls; internal entrances are unconfirmed.')
    positioned = position is not None
    if positioned:
        floor = position['floor']
    return {
        'id': stable_id(key), 'map_key': key, 'name': name, 'category': CATEGORIES[record['type']],
        'block': 'Block ' + record['block'] if record.get('block') else 'Campus spine',
        'floor': f'Floor {floor}' if floor is not None else 'Floor unknown',
        'map_floor': floor, 'floors': floors, 'has_position': positioned,
        'x': position['x'] / layout.WIDTH if positioned else 0,
        'y': position['y'] / layout.HEIGHT if positioned else 0,
        'geometry': position['geometry'] if positioned else None,
        'access': record.get('access', 'public'),
        'notes': ' '.join(n for n in notes if n),
        'position_status': TRACED if positioned else 'Not positioned',
        'opening_hours': 'Not confirmed', 'contact': 'Not confirmed',
        'accessible': False, 'accessibility_status': 'Not verified',
        'aliases': ','.join(record.get('aliases', []) + record.get('services', []) + [key.replace('_', ' ')]),
        'access_via': record.get('access_via', []),
        'skips_floors': record.get('skips_floors', []),
        'entrances_from_floors': record.get('entrances_from_floors', []),
    }


def generated_place(key, position, catalogue):
    record = dict(position['record'])
    base = catalogue.get(record.pop('base', None), {})
    floor = position['floor']
    name = record.pop('name')
    aliases = [name.lower(), key.replace('_', ' ')]
    if record.get('category') == 'Classroom':
        aliases.append(f'room {name}')
    return {
        'id': stable_id(key), 'map_key': key, 'name': name,
        'category': record.pop('category', CATEGORIES.get(base.get('type'), 'Stairs')),
        'block': record.pop('block', 'Block ' + base['block'] if base.get('block') else 'Campus spine'),
        'floor': f'Floor {floor}', 'map_floor': floor,
        'floors': record.pop('floors', None) or base.get('connects_floors', [floor]),
        'has_position': True, 'x': position['x'] / layout.WIDTH, 'y': position['y'] / layout.HEIGHT,
        'geometry': position['geometry'], 'access': 'public',
        'notes': record.pop('notes', None) or 'Landing traced from the evacuation plan; position approximate.',
        'position_status': TRACED, 'opening_hours': 'Not confirmed', 'contact': 'Not confirmed',
        'accessible': False, 'accessibility_status': 'Not verified', 'aliases': ','.join(aliases),
        'access_via': [], 'skips_floors': record.pop('skips_floors', []), 'entrances_from_floors': [],
    }


# ---------------------------------------------------------------------------
# SVG backgrounds
# ---------------------------------------------------------------------------

PLATE, OUTLINE = '#e8ecf2', '#7f8a9e'


def pts(points):
    return ' '.join(f'{x:g},{y:g}' for x, y in points)


def mix(color, amount):
    """Blend a #rrggbb colour toward white."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return '#%02x%02x%02x' % tuple(round(c + (255 - c) * amount) for c in (r, g, b))


def text(x, y, value, size=10, weight=600, fill='#2c3a52'):
    return (f'<text x="{x:g}" y="{y:g}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="middle" stroke="#ffffff" stroke-width="3" '
            f'stroke-opacity=".75" paint-order="stroke">{escape(value)}</text>')


def svg_floor(floor, shapes):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.WIDTH}" height="{layout.HEIGHT}" '
           f'viewBox="0 0 {layout.WIDTH} {layout.HEIGHT}">',
           f'<title>SDU main building, floor {floor} (schematic)</title>',
           '<defs>'
           '<pattern id="void" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
           '<rect width="8" height="8" fill="#f3f5f8"/><line x1="0" y1="0" x2="0" y2="8" stroke="#c3cad6" stroke-width="2"/></pattern>'
           '<pattern id="steps" width="4" height="4" patternUnits="userSpaceOnUse">'
           '<rect width="4" height="4" fill="#ffffff"/><rect width="4" height="1.6" fill="#7b869a"/></pattern>'
           '</defs>']
    by = lambda *kinds: [s for s in shapes if s['kind'] in kinds]
    def void(s):
        if s.get('outline_only'):
            return [f'<polygon points="{pts(s["points"])}" fill="none" stroke="#a7b0bf" stroke-dasharray="5 4"/>']
        drawn = [f'<polygon points="{pts(s["points"])}" fill="url(#void)" stroke="#a7b0bf" stroke-dasharray="5 4"/>']
        if s.get('rings'):
            cx, cy = layout.centroid(s['points'])
            drawn += [f'<circle cx="{cx:g}" cy="{cy - 4:g}" r="{r}" fill="none" stroke="#b8c0cd"/>' for r in (14, 22, 30, 38)]
        return drawn
    for s in by('void'):
        if s.get('under'):
            out += void(s)
    # Plates are drawn twice so overlapping pieces share one outline.
    for width, colour in ((3.2, OUTLINE), (0, PLATE)):
        for s in by('plate', 'bridge'):
            if s['kind'] == 'bridge':
                (x1, y1), (x2, y2) = s['points']
                out.append(f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{colour}" '
                           f'stroke-width="{s["w"] + width:g}" stroke-linecap="butt"/>')
            else:
                stroke = f' stroke="{colour}" stroke-width="{width:g}" stroke-linejoin="round"' if width else ''
                out.append(f'<polygon points="{pts(s["points"])}" fill="{PLATE}"{stroke}/>')
    for s in by('void'):
        if not s.get('under'):
            out += void(s)
    for s in by('wing'):
        out.append(f'<polygon points="{pts(s["points"])}" fill="{s["color"]}" stroke="{s["color"]}" stroke-width="1.5"/>')
    for s in by('room', 'column', 'core'):
        if s['kind'] == 'room' and s.get('color'):
            fill, stroke = mix(s['color'], .45), s['color']
        else:
            fill, stroke = {'room': ('#f3f5f9', '#9aa4b5'), 'column': ('#d9dee6', '#9aa4b5'),
                            'core': ('#cbd2dc', '#9aa4b5')}[s['kind']]
        out.append(f'<polygon points="{pts(s["points"])}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
    for s in by('feature'):
        out.append(f'<polygon points="{pts(s["points"])}" fill="{s["fill"]}" stroke="#00000040" stroke-width="1"/>')
        if s.get('rings'):
            cx, cy = layout.centroid(s['points'])
            out += [f'<circle cx="{cx:g}" cy="{cy - 4:g}" r="{r}" fill="none" stroke="#ffffff80" stroke-width="1.5"/>'
                    for r in (12, 20, 28, 36)]
        if s.get('seats'):
            (x0, y0), (x1, _), (_, y1) = s['points'][0], s['points'][1], s['points'][2]
            for y in range(int(y0) + 14, int(y1) - 6, 9):
                out.append(f'<line x1="{x0 + 12:g}" y1="{y}" x2="{x1 - 22:g}" y2="{y}" stroke="#ffffff59" stroke-width="2"/>')
    for s in by('bochka', 'bochka_upper', 'bochka_top', 'circle_room', 'spiral'):
        (x, y), r = s['points'][0], s['r']
        fill, stroke = {'bochka': ('#d9b45a', '#9c7c32'), 'bochka_upper': ('#ead49a', '#9c7c32'),
                        'bochka_top': ('#f3e8c8', '#9c7c32'), 'circle_room': ('#d3d9e2', '#9aa4b5'),
                        'spiral': ('#ffffff', '#6b778a')}[s['kind']]
        out.append(f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        if s.get('label') and s['kind'].startswith('bochka'):
            out.append(text(x, y + r * .62, s['label'], size=10, weight=700, fill='#5a4514'))
        if s['kind'] in ('bochka', 'bochka_upper'):
            for k in range(3):
                rr = r * (0.82 - k * 0.16)
                out.append(f'<path d="M{x - rr:g} {y + 4:g} A{rr:g} {rr:g} 0 0 1 {x + rr:g} {y + 4:g}" fill="none" '
                           f'stroke="#ffffff99" stroke-width="2"/>')
        if s['kind'] == 'spiral':
            out.append(f'<path d="M{x:g} {y:g} m-3 0 a3 3 0 1 1 6 0 a6 6 0 1 1 -12 0 a9 9 0 1 1 18 0" '
                       f'fill="none" stroke="#6b778a" stroke-width="1.4"/>')
    for s in by('stairs'):
        out.append(f'<polygon points="{pts(s["points"])}" fill="url(#steps)" stroke="#6b778a" stroke-width="1"/>')
    for s in by('curved_stairs'):
        (x, y), r = s['points'][0], s['r']
        out.append(f'<path d="M{x:g} {y - r:g} A{r:g} {r:g} 0 0 0 {x:g} {y + r:g}" fill="none" stroke="#7b869a" '
                   f'stroke-width="9" stroke-dasharray="1.6 2.2"/>')
        out.append(f'<path d="M{x:g} {y - r - 4.5:g} A{r + 4.5:g} {r + 4.5:g} 0 0 0 {x:g} {y + r + 4.5:g}" fill="none" '
                   f'stroke="#6b778a" stroke-width="1"/>')
    for s in by('exit'):
        x, y = s['points'][0]
        out.append(f'<rect x="{x - 4:g}" y="{y - 4:g}" width="8" height="8" rx="1.5" fill="#2f9e5a"/>')
    for s in shapes:
        if s.get('label') and s['kind'] not in ('bochka', 'bochka_upper', 'bochka_top'):
            cx, cy = layout.centroid(s['points'])
            out.append(text(cx, cy + 18 if s['kind'] == 'feature' else cy + 4, s['label'],
                            size=10 if s['kind'] != 'void' else 9, weight=600 if s['kind'] == 'feature' else 400,
                            fill='#2c3a52' if s['kind'] == 'feature' else '#5d6a80'))
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main():
    bundle = Path(sys.argv[1])
    data = yaml.safe_load((bundle / 'campus.yaml').read_text())
    built = layout.build()
    records = data['places'] + data['structures'] + data['vertical_infrastructure']
    catalogue = {r['id']: r for r in records}
    places, attachments = [], {}
    for record in records:
        if record.get('retired'):
            continue
        position = built.places.get(record['id'])
        places.append(catalogue_place(record, position))
        if position and position['node']:
            attachments[record['id']] = position['node']
    for key, position in built.places.items():
        if key in catalogue:
            continue
        assert position['record'], f'{key} has no catalogue record'
        places.append(generated_place(key, position, catalogue))
        attachments[key] = position['node']
    keys = {p['map_key'] for p in places}
    assert len({p['id'] for p in places}) == len(places)
    assert set(built.places) <= keys
    assert all(e['a'] in built.nodes and e['b'] in built.nodes for e in built.edges)
    assert all(node in built.nodes for node in attachments.values())
    for p in places:  # an attachment must be on the place's floor
        if p['map_key'] in attachments:
            assert built.node_floors[attachments[p['map_key']]] == p['map_floor'], p['map_key']
    for e in built.edges:
        a, b = built.node_floors[e['a']], built.node_floors[e['b']]
        assert (a == b) == (e['kind'] == 'corridor'), e
        assert math.dist(built.nodes[e['a']], built.nodes[e['b']]) > 0 or e['kind'] != 'corridor', e
    routing = {'status': 'schematic_draft', 'nodes': built.nodes, 'node_floors': built.node_floors,
               'edges': built.edges, 'attachments': attachments}
    payload = {'version': 3, 'width': layout.WIDTH, 'height': layout.HEIGHT, 'mapped_floors': FLOORS,
               'labels': built.labels, 'routing_status': routing['status'], 'routing': routing, 'places': places}
    asset = ROOT / 'assets/maps'
    for floor in FLOORS:
        (asset / f'floor-{floor}-background.svg').write_text(svg_floor(floor, built.shapes[floor]))
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
    (asset / 'campus.json').write_text(encoded)
    (ROOT / 'backend/app/data/campus.json').write_text(encoded)
    print(f'Imported {len(places)} records; {sum(p["has_position"] for p in places)} positioned on floors 1-3; '
          f'{len(built.nodes)} graph nodes, {len(built.edges)} connections.')


if __name__ == '__main__':
    main()
