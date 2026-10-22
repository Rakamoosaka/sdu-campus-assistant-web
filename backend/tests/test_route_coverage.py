"""Exhaustively check the explicit graph, including floor transfers and reverse trips."""
from collections import Counter
from app import main as m
from app.routing import draft_route


def test_every_positioned_public_place_has_an_explicit_approach():
    campus = m.CAMPUS_MAP
    public = [p for p in campus['places'] if p['has_position'] and p.get('access', 'public') == 'public']
    assert len(public) == 88
    assert all(p['map_key'] in campus['routing']['attachments'] for p in public)
    assert all(campus['routing']['node_floors'][campus['routing']['attachments'][p['map_key']]] == p['map_floor'] for p in public)


def test_all_public_start_destination_pairs_and_stairs_exclusion():
    campus = m.CAMPUS_MAP
    public = [p for p in campus['places'] if p['map_key'] in campus['routing']['attachments'] and p.get('access', 'public') == 'public']
    graph = campus['routing']
    edges = {frozenset((e['a'], e['b'])): e for e in graph['edges']}
    results = Counter()
    for avoid_stairs in (False, True):
        for start in public:
            for target in public:
                route = draft_route(campus, start['id'], target['id'], avoid_stairs)
                status = route['status']
                results[status] += 1
                if avoid_stairs and any(p['category'] == 'Stairs' for p in (start, target)):
                    assert status == 'no_step_free_route'
                elif start['id'] == target['id']:
                    assert status == 'same_location'
                elif avoid_stairs and (start['map_floor'] == 3 or target['map_floor'] == 3):
                    assert status == 'no_route'
                else:
                    assert status == 'schematic_draft', (start['name'], target['name'], route)
                    assert route['segments'] and route['steps']
                    assert route['segments'][0]['floor'] == start['map_floor']
                    assert route['segments'][-1]['floor'] == target['map_floor']
                    assert route['node_path'][0] == graph['attachments'][start['map_key']]
                    assert route['node_path'][-1] == graph['attachments'][target['map_key']]
                    for a, b in zip(route['node_path'], route['node_path'][1:]):
                        assert frozenset((a, b)) in edges
                        if avoid_stairs:
                            assert edges[frozenset((a, b))]['kind'] != 'stairs'
                    for segment in route['segments']:
                        assert len(segment['from']) == len(segment['to']) == 2
                    assert route['distance_m'] is None and route['duration_min'] is None
    assert sum(results.values()) == 2 * 89 * 89


def test_new_destinations_route_through_api_and_reverse(api_client):
    ids = {p['map_key']: p['id'] for p in m.CAMPUS_MAP['places']}
    for key in ['main_canteen', 'canteen_shop', 'red_canteen', 'mini_red_hall', 'table_tennis_zone', 'print_shop', 'entrance_g']:
        forward = api_client.get('/routes', params={'start': 1, 'destination': ids[key]}).json()
        backward = api_client.get('/routes', params={'start': ids[key], 'destination': 1}).json()
        assert forward['status'] == backward['status'] == 'schematic_draft'
        assert forward['node_path'] == list(reversed(backward['node_path']))
        assert forward['destination_location_id'] == ids[key]
        assert backward['start_location_id'] == ids[key]
    staff = next(p for p in m.CAMPUS_MAP['places'] if p.get('access') == 'staff')
    assert api_client.get('/routes', params={'destination': staff['id']}).json()['status'] == 'restricted'
