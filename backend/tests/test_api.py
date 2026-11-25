import copy
import os



from fastapi.testclient import TestClient
from app import main as m
from app.main import app, seed_database


import pytest

@pytest.fixture(autouse=True)
def client_fixture(api_client):
    global client
    client = api_client


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_map_facts_and_no_fabricated_routes():
    data = client.get('/campus-map').json()
    assert data['mapped_floors'] == [1, 2, 3]
    assert len(data['places']) == 145
    assert not any(p['map_key'] in {'h103', 'h104', 'h203', 'h204'} for p in data['places'])
    assert not any(p['map_key'] == 'stair_main_01' for p in data['places'])
    for block in ['d', 'f', 'h']:
        lift = next(p for p in data['places'] if p['map_key'] == f'lift_block_{block}')
        assert lift['floors'] == [-1, 1, 2, 3]
        assert lift['has_position'] is True
    stair = next(p for p in data['places'] if p['map_key'] == 'stair_main_06')
    assert stair['floors'] == [1, 3]
    assert stair['skips_floors'] == [2]
    route = client.get('/routes', params={'destination': 2, 'accessible': True}).json()
    assert route['status'] == 'schematic_draft'
    assert route['steps']
    assert route['accessibility_verified'] is False
    assert route['distance_m'] is None
    assert route['duration_min'] is None


def test_d101_route_follows_corridor_and_reverse_path():
    data = client.get('/campus-map').json()
    target = next(p for p in data['places'] if p['map_key'] == 'd101')['id']
    route = client.get('/routes', params={'destination': target}).json()
    assert route['status'] == 'schematic_draft'
    assert route['node_path'] == ['f1_c_entrance', 'f1_c_wing', 'f1_c_east', 'f1_c_hub', 'f1_spine_1250', 'f1_spine_1205',
                                  'f1_spine_1188', 'f1_spine_1124', 'f1_d_root', 'f1_d_room_1']
    assert route['segments'][-1]['approximate_door'] is True
    assert route['segments'][0]['approximate_door'] is True
    reverse = client.get('/routes', params={'start': target, 'destination': 1}).json()
    assert reverse['node_path'] == list(reversed(route['node_path']))
    assert reverse['points'] == list(reversed(route['points']))


def test_unknown_floor_same_location_and_stairs_are_not_fabricated():
    data = client.get('/campus-map').json()
    ids = {p['map_key']: p['id'] for p in data['places']}
    for key in ['library_stairs', 'library_lift', 'technopark']:
        route = client.get('/routes', params={'destination': ids[key]}).json()
        assert route['status'] == 'unmapped'
        assert route['points'] == []
    assert client.get('/routes?destination=1&start=1').json()['status'] == 'same_location'
    blocked = client.get('/routes', params={'destination': ids['stair_main_03'], 'accessible': True}).json()
    assert blocked['status'] == 'no_step_free_route'
    lift = client.get('/routes', params={'destination': ids['lift_block_d'], 'accessible': True}).json()
    assert lift['status'] == 'schematic_draft'
    assert lift['accessibility_verified'] is False
    assert lift['floor'] == 1


def test_second_floor_routes_use_stairs_or_lifts_by_preference():
    data = client.get('/campus-map').json()
    ids = {p['map_key']: p['id'] for p in data['places']}
    normal = client.get('/routes', params={'destination': ids['d201']}).json()
    accessible = client.get('/routes', params={'destination': ids['d201'], 'accessible': True}).json()
    assert normal['status'] == accessible['status'] == 'schematic_draft'
    assert any(t['kind'] == 'stairs' for t in normal['transfers'])
    assert accessible['transfers'] and all(t['kind'] == 'lift' for t in accessible['transfers'])
    assert normal['route_floors'] == accessible['route_floors'] == [1, 2]
    assert {s['floor'] for s in accessible['segments']} == {1, 2}
    assert accessible['accessibility_verified'] is False
    for block in 'defgh':
        for floor in [1, 2, 3]:
            for room in range(1, 3 if block == 'h' else 5):
                assert client.get('/routes', params={'destination': ids[f'{block}{floor}0{room}']}).json()['status'] == 'schematic_draft'
    canteen = client.get('/routes', params={'start': ids['d201'], 'destination': ids['canteen_floor_3']}).json()
    assert [t['label'] for t in canteen['transfers']] == ['Canteen stairs']
    lift = client.get('/routes', params={'destination': ids['canteen_floor_3'], 'accessible': True}).json()
    assert lift['status'] == 'schematic_draft' and lift['route_floors'][-1] == 3
    assert lift['transfers'] and all(t['kind'] == 'lift' for t in lift['transfers'])
    # Without the lifts, an upper floor has no step-free route and the user is told why.
    no_lifts = copy.deepcopy(m.CAMPUS_MAP)
    no_lifts['routing']['edges'] = [e for e in no_lifts['routing']['edges'] if e['kind'] != 'lift']
    blocked = m.draft_route(no_lifts, 1, ids['d201'], True)
    assert blocked['status'] == 'no_step_free_route'
    assert 'Turn off Avoid stairs' in blocked['message']


def test_floor_three_is_mapped_from_the_evacuation_plans():
    data = client.get('/campus-map').json()
    places = {p['map_key']: p for p in data['places']}
    floors = data['routing']['node_floors']
    assert {p['map_floor'] for p in data['places'] if p['has_position']} == {1, 2, 3}
    assert places['canteen_floor_3']['has_position'] and places['canteen_floor_3']['map_floor'] == 3
    for key in ('d301', 'h302', 'bochka_2_floor_3', 'stair_block_b_floor_3', 'lift_block_f_floor_3'):
        assert places[key]['map_floor'] == 3 and floors[data['routing']['attachments'][key]] == 3
    # Staircase 6 still skips floor 2; the canteen stairs only link floors 2 and 3.
    s6 = [e for e in data['routing']['edges'] if e['label'].startswith('Staircase 6')]
    assert s6 and all({floors[e['a']], floors[e['b']]} == {1, 3} for e in s6)
    canteen = [e for e in data['routing']['edges'] if e['label'] == 'Canteen stairs']
    assert canteen and all({floors[e['a']], floors[e['b']]} == {2, 3} for e in canteen)
    # Every block has an end staircase on floors 1-3 and D105/D106 sit in Block D's angled wing.
    for block in 'defgh':
        assert places[f'stair_block_{block}']['has_position']
        assert places[f'stair_block_{block}_floor_3']['map_floor'] == 3
    assert places['d105']['has_position'] and places['d105']['map_floor'] == 1
    route = client.get('/routes', params={'destination': places['d106']['id']}).json()
    assert route['status'] == 'schematic_draft' and route['node_path'][-1] == data['routing']['attachments']['d106']


def test_search_confirmed_room_and_no_fake_parking():
    assert any(p['name'] == 'D101' for p in client.get('/search?q=D101').json())
    assert client.get('/search?q=Parking').json() == []
    answer = client.post('/assistant/query', json={'question': 'Where can I park?'}).json()
    assert answer['location'] is None


def test_student_role_and_map_data():
    login = client.post(
        "/auth/login",
        json={"sdu_id": "240103049", "password": "Campus123!"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "student"
    locations = client.get("/locations")
    assert locations.status_code == 200
    assert any(item["name"] == "D101" for item in locations.json())
    assert not any(item["name"] == "Room 317" for item in locations.json())


def test_admin_role_override():
    login = client.post(
        "/auth/login",
        json={"sdu_id": "240000002", "password": "Campus123!"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "admin"


def test_preferences_and_favorites_are_persisted():
    login = client.post(
        "/auth/login",
        json={"sdu_id": "240103050", "password": "Campus123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    preference = client.put(
        "/users/me/preferences",
        json={"accessible_routes": True},
        headers=headers,
    )
    assert preference.status_code == 200
    assert client.get("/users/me/preferences", headers=headers).json()["accessible_routes"] is True

    saved = client.post("/users/me/favorites/2", headers=headers)
    assert saved.status_code == 201
    favorites = client.get("/users/me/favorites", headers=headers).json()
    assert any(item["id"] == 2 for item in favorites)


def test_registration_requires_password_and_assigns_student_role():
    response = client.post(
        "/auth/register",
        json={
            "sdu_id": "250999991",
            "full_name": "New Student",
            "password": "StrongPass1!",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "student"


def test_wrong_password_is_rejected():
    response = client.post(
        "/auth/login",
        json={"sdu_id": "240103049", "password": "definitely-wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect ID or password"


def test_favorites_limit_duplicate_and_replacement():
    registration = client.post('/auth/register', json={
        'sdu_id': '250999992', 'full_name': 'Favorite Limit Test', 'password': 'StrongPass1!'})
    assert registration.status_code == 201
    headers = {'Authorization': f"Bearer {registration.json()['access_token']}"}
    for saved in client.get('/users/me/favorites', headers=headers).json():
        client.delete(f"/users/me/favorites/{saved['id']}", headers=headers)
    ids = [p['id'] for p in client.get('/campus-map').json()['places'][:6]]
    for place in ids[:5]:
        assert client.post(f'/users/me/favorites/{place}', headers=headers).status_code == 201
    assert client.post(f'/users/me/favorites/{ids[0]}', headers=headers).status_code == 201
    full = client.post(f'/users/me/favorites/{ids[5]}', headers=headers)
    assert full.status_code == 409
    assert 'up to 5' in full.json()['detail']
    assert len(client.get('/users/me/favorites', headers=headers).json()) == 5
    client.delete(f'/users/me/favorites/{ids[0]}', headers=headers)
    assert client.post(f'/users/me/favorites/{ids[5]}', headers=headers).status_code == 201
    assert len(client.get('/users/me/favorites', headers=headers).json()) == 5
