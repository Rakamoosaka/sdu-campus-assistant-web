from sqlalchemy import create_engine, inspect, text
from app import main as m


def login(client, who='240103049'):
    result = client.post('/auth/login', json={'sdu_id': who, 'password': 'Campus123!'})
    client.cookies.clear()
    return {'Authorization': 'Bearer ' + result.json()['access_token']}


def guest(client):
    token = client.post('/auth/guest').json()['access_token']
    client.cookies.clear()
    return {'Authorization': 'Bearer ' + token}


IDS = {p['map_key']: p['id'] for p in m.CAMPUS_MAP['places']}


def test_campus_map_identifies_stairs_lifts_entrances_and_step_free_connections(api_client):
    data = api_client.get('/campus-map').json()
    kinds = {row['kind']: row['step_free'] for row in data['network']}
    assert kinds == {'corridor': True, 'lift': True, 'stairs': False}
    places = {p['map_key']: p for p in data['places']}
    assert places['entrance_c_main']['category'] == 'Entrance'
    assert places['entrance_c_main']['step_free_access'] == 'Not verified'
    assert places['lift_block_d']['category'] == 'Lift'


def test_guest_saved_preference_and_anonymous_query(api_client):
    c = api_client; h = guest(c)
    assert c.put('/users/me/preferences', headers=h, json={'accessible_routes': True}).json()['saved_for'] == 'guest_session'
    route = c.get('/routes', headers=h, params={'destination': IDS['d201']}).json()
    assert route['avoid_stairs'] is True and all(t['kind'] == 'lift' for t in route['transfers'])
    assert all(row['step_free'] for row in route['connections'])
    assert any('not verified' in w for w in route['warnings'])
    assert c.get('/routes', params={'destination': IDS['d201'], 'accessible': True}).json()['avoid_stairs'] is True
    assert c.get('/routes', headers=guest(c), params={'destination': IDS['d201']}).json()['avoid_stairs'] is False


def test_entrance_marked_not_step_free_explains_no_route(api_client):
    c = api_client; admin = login(c, '240000002'); student = login(c)
    entrance = c.get(f"/locations/{IDS['entrance_c_main']}").json()
    assert c.put(f"/admin/locations/{entrance['id']}", headers=admin, json={**entrance, 'step_free_access': 'Maybe'}).status_code == 422
    assert c.put(f"/admin/locations/{entrance['id']}", headers=admin, json={**entrance, 'step_free_access': 'Not step-free'}).status_code == 200
    c.put('/users/me/preferences', headers=student, json={'accessible_routes': True})
    route = c.get('/routes', headers=student, params={'start': entrance['id'], 'destination': IDS['d201']}).json()
    assert route['status'] == 'no_step_free_route' and 'Main Entrance' in route['message']
    c.put(f"/admin/locations/{entrance['id']}", headers=admin, json={**entrance, 'step_free_access': 'Step-free'})
    route = c.get('/routes', headers=student, params={'start': entrance['id'], 'destination': IDS['d201']}).json()
    assert route['status'] == 'schematic_draft'
    assert 'Main Entrance is recorded as having step-free access.' in route['warnings']


def test_blocked_path_report_closure_tracking_and_reopen(api_client):
    c = api_client; student = login(c); admin = login(c, '240000002')
    route = c.get('/routes', params={'destination': IDS['d201']}).json()
    blocked = route['connections'][2]
    body = {'kind': 'path', 'message': 'Corridor blocked by renovation', 'edge_a': blocked['a'], 'edge_b': blocked['b'],
            'route_start_id': 1, 'route_destination_id': IDS['d201']}
    assert c.post('/reports', headers=student, json={**body, 'edge_b': 'nowhere'}).status_code == 422
    assert c.post('/reports', headers=student, json={**body, 'kind': 'other'}).status_code == 422
    assert c.post('/reports', headers=student, json={'message': 'Wrong', 'kind': 'location'}).status_code == 422
    report = c.post('/reports', headers=student, json=body).json()
    assert report['connection_label'] == blocked['label'] and report['status'] == 'new'
    assert c.post('/admin/path-status', headers=student, json={'edge_a': blocked['a'], 'edge_b': blocked['b'], 'state': 'closed'}).status_code == 403
    listed = c.get('/admin/reports', headers=admin).json()[0]
    assert listed['id'] == report['id'] and listed['kind'] == 'path'
    closure = c.post('/admin/path-status', headers=admin, json={'edge_a': blocked['a'], 'edge_b': blocked['b'], 'state': 'closed', 'report_id': report['id']}).json()
    mine = c.get('/reports/me', headers=student).json()[0]
    assert mine['status'] == 'resolved' and 'closed' in mine['resolution_note']
    assert mine['path_status'] == {'id': closure['id'], 'state': 'closed'}
    rerouted = c.get('/routes', params={'destination': IDS['d201']}).json()
    assert {blocked['a'], blocked['b']} not in [{x['a'], x['b']} for x in rerouted['connections']]
    network = c.get('/campus-map').json()['network']
    assert any(row['closed'] and {row['a'], row['b']} == {blocked['a'], blocked['b']} for row in network)
    assert c.get('/admin/path-status', headers=admin).json()[0]['id'] == closure['id']
    assert c.delete(f"/admin/path-status/{closure['id']}", headers=admin).json()['reopened'] is True
    assert c.get('/routes', params={'destination': IDS['d201']}).json()['connections'] == route['connections']
    assert c.get('/reports/me', headers=student).json()[0]['path_status'] is None


def test_closure_that_disconnects_explains_why(api_client):
    c = api_client; admin = login(c, '240000002')
    for edge in m.CAMPUS_MAP['routing']['edges']:
        if 'f3_canteen' in (edge['a'], edge['b']):
            c.post('/admin/path-status', headers=admin, json={'edge_a': edge['a'], 'edge_b': edge['b'], 'state': 'closed'})
    result = c.get('/routes', params={'start': IDS['d201'], 'destination': IDS['canteen_floor_3']}).json()
    assert result['status'] == 'no_route' and 'reported path is closed' in result['message']


def test_not_step_free_mark_only_affects_step_free_routes(api_client):
    c = api_client; admin = login(c, '240000002')
    route = c.get('/routes', params={'destination': IDS['d201'], 'accessible': True}).json()
    lift = next(x for x in route['connections'] if x['kind'] == 'lift')
    c.post('/admin/path-status', headers=admin, json={'edge_a': lift['a'], 'edge_b': lift['b'], 'state': 'not_step_free'})
    detour = c.get('/routes', params={'destination': IDS['d201'], 'accessible': True}).json()
    assert detour['status'] == 'schematic_draft' and lift['label'] not in [t['label'] for t in detour['transfers']]
    assert c.get('/routes', params={'destination': IDS['d201']}).json()['status'] == 'schematic_draft'


def test_guest_reports_location_admin_note_and_updated_details(api_client):
    c = api_client; visitor = guest(c); admin = login(c, '240000002')
    report = c.post('/reports', headers=visitor, json={'kind': 'location', 'location_id': 2, 'message': 'Hours are wrong'}).json()
    assert c.get('/reports/me', headers=login(c)).json() == []
    location = c.get('/locations/2').json()
    c.put('/admin/locations/2', headers=admin, json={**location, 'opening_hours': '09:00–17:00'})
    assert c.put(f"/admin/reports/{report['id']}", headers=admin, json={'status': 'resolved', 'resolution_note': 'x' * 1001}).status_code == 422
    updated = c.put(f"/admin/reports/{report['id']}", headers=admin, json={'status': 'resolved', 'resolution_note': 'Hours corrected.'}).json()
    assert updated['updated_at'] and updated['location_name']
    mine = c.get('/reports/me', headers=visitor).json()[0]
    assert mine['status'] == 'resolved' and mine['resolution_note'] == 'Hours corrected.'
    assert c.get('/locations/2').json()['opening_hours'] == '09:00–17:00'


def test_existing_database_gains_new_columns(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "old.db"}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE inaccuracyreport (id INTEGER PRIMARY KEY, author VARCHAR NOT NULL, location_id INTEGER, '
                                'message VARCHAR NOT NULL, status VARCHAR NOT NULL, created_at DATETIME NOT NULL)'))
        connection.execute(text("INSERT INTO inaccuracyreport VALUES (1, '240103049', 2, 'Old report', 'new', '2026-01-01 00:00:00')"))
    monkeypatch.setattr(m, 'engine', engine)
    m.seed_database()
    columns = {c['name'] for c in inspect(engine).get_columns('inaccuracyreport')}
    assert {'kind', 'edge_a', 'resolution_note', 'updated_at'} <= columns
    assert 'step_free_access' in {c['name'] for c in inspect(engine).get_columns('location')}
    with engine.connect() as connection:
        assert connection.execute(text('SELECT kind, resolution_note FROM inaccuracyreport')).one() == ('location', '')
