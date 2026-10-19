"""Create a floor-1 reference overlay for the user's floor-2 drawing, not a floor-2 map."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
ns = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', ns[1:-1])
svg = ET.Element(ns + 'svg', width='1490', height='1490', viewBox='0 0 1490 1490')
def element(tag, **attrs):
    return ET.SubElement(svg, ns + tag, {k.replace('_', '-'): str(v) for k, v in attrs.items()})
def text(x, y, value, size=16, color='#101a4d', weight='normal'):
    element('text', x=x, y=y, font_size=size, fill=color, font_family='Arial', font_weight=weight).text = value
element('rect', width=1490, height=1490, fill='white')
text(25, 35, 'SDU — FLOOR 2 DRAWING TEMPLATE', 25, weight='bold')
text(25, 62, 'Floor-1 geometry underneath: change it wherever floor 2 differs.', 17)
text(25, 86, 'Markers show floor-1 reference positions, NOT confirmed floor-2 landings.', 16)
data = json.loads((root / 'assets/maps/campus.json').read_text())
background = ET.parse(root / 'assets/maps/floor-1-background.svg').getroot()
group = element('g', transform='translate(15 110)')
background.set('opacity', '.55')
group.append(background)
for label in data['labels']:
    t = ET.SubElement(group, ns + 'text', {'x': str(label['x']), 'y': str(label['y']),
        'fill': label['color'], 'font-size': str(label['size']), 'font-family': 'Arial',
        'text-anchor': label['align'], 'font-weight': 'bold'})
    t.text = label['text']
for p in data['places']:
    if not p['has_position'] or p['category'] not in ['Stairs', 'Lift']:
        continue
    key = p['map_key']
    code = ('S' + str(int(key.split('_')[-1])) if key.startswith('stair_main_') else
            'L-' + p['block'][-1] if key.startswith('lift_block_') else
            'S-D' if key == 'stair_block_d' else 'SP')
    x, y = p['x'] * 765 + 15, p['y'] * 1280 + 110
    color = '#c13a35' if code == 'S6' else '#156de5' if p['category'] == 'Lift' else '#101a4d'
    element('circle', cx=x, cy=y, r=22, fill='white', stroke=color, stroke_width=3)
    t = element('text', x=x, y=y+6, text_anchor='middle', font_family='Arial', font_size=16,
                font_weight='bold', fill=color)
    t.text = code
    if code == 'S6':
        text(x+28, y-25, 'NO FLOOR-2', 13, color, 'bold')
        text(x+28, y-8, 'LANDING', 13, color, 'bold')
text(795, 135, 'REFERENCE KEY', 20, weight='bold')
lines = [
    'S1, S3, S4, S5, S8: main stairs',
    'S6: floors 1 → 3 only; skips 2',
    'S-D: Block D end stairs',
    'SP: spiral stairs by Bochkas',
    'L-D / L-F / L-H: corridor lifts',
    '',
    'PLEASE DRAW / CONFIRM',
    '• Floor-2 corridors and junctions',
    '• Actual stair and lift landings',
    '• Room codes and door positions',
    '• Steps / locked or staff doors',
    '• Library and Bochka connections',
    '• Mark uncertain details with ?',
    '',
    'UNPOSITIONED — ADD THESE',
    'Block E/F/G/H end stairs:',
    'known, but exact positions unknown.',
    'Label them S-E, S-F, S-G, S-H.',
    '',
    'Library internal stairs and lift:',
    'positions unknown; draw if recalled.',
    'Label S-LIB and L-LIB.',
    '',
    'Leave unknown areas blank.',
    'No need to draw every room.',
]
for i, line in enumerate(lines):
    text(795, 170+i*28, line, 14, weight='bold' if line.isupper() else 'normal')
text(25, 1430, 'Draw over this reference. It is not a surveyed floor-2 plan; distances are not to scale.', 17)
text(25, 1460, 'Include at least one confirmed floor-2 classroom and its doorway for the first cross-floor route.', 16)
out = root / 'docs/floor-2-drawing-template.svg'
ET.ElementTree(svg).write(out, encoding='unicode')
print(out)
