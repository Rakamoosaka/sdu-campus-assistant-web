import os



from fastapi.testclient import TestClient
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
    assert data['mapped_floors'] == [1, 2]
    assert len(data['places']) == 103
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
    assert route['node_path'] == ['entrance_c', 'atrium_east', 'atrium', 'lower_hub', 'spine_950', 'spine_d', 'room_approach_d101']
    assert route['segments'][-1]['approximate_door'] is True
    assert route['segments'][0]['approximate_door'] is True
    reverse = client.get('/routes', params={'start': target, 'destination': 1}).json()
    assert reverse['node_path'] == list(reversed(route['node_path']))
    assert reverse['points'] == list(reversed(route['points']))


def test_unknown_floor_same_location_and_stairs_are_not_fabricated():
    data = client.get('/campus-map').json()
    ids = {p['map_key']: p['id'] for p in data['places']}
    for key in ['d105', 'library_lift', 'technopark']:
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
        for floor in [1, 2]:
            for room in range(1, 5):
                assert client.get('/routes', params={'destination': ids[f'{block}{floor}0{room}']}).json()['status'] == 'schematic_draft'
    canteen = client.get('/routes', params={'start': ids['d201'], 'destination': ids['canteen_floor_3']}).json()
    assert any(t['label'] == 'Canteen stairs' for t in canteen['transfers'])
    blocked = client.get('/routes', params={'destination': ids['canteen_floor_3'], 'accessible': True}).json()
    assert blocked['status'] == 'no_route'


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
