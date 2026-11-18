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
    assert mine['path_status'] == {'id': closure['id'], 'state': 'closed', 'reopens_at': None}
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
    assert {'starts_at', 'ends_at'} <= {c['name'] for c in inspect(engine).get_columns('announcement')}
    with engine.connect() as connection:
        assert connection.execute(text('SELECT kind, resolution_note FROM inaccuracyreport')).one() == ('location', '')


def test_admin_edits_details_only_and_keeps_map_import(api_client):
    c = api_client; admin = login(c, '240000002')
    library = c.get('/locations/2').json()
    assert c.post('/admin/locations', headers=admin, json=library).status_code == 404
    body = {**library, 'category': 'Stairs', 'x': 0.01, 'y': 0.01, 'aliases': 'books, quiet room', 'opening_hours': '08:00–20:00'}
    edited = c.put('/admin/locations/2', headers=admin, json=body).json()
    assert (edited['category'], edited['x'], edited['y']) == (library['category'], library['x'], library['y'])
    assert edited['opening_hours'] == '08:00–20:00'
    assert edited['aliases'].split(',')[:2] == ['books', 'quiet room'] and edited['aliases'].endswith(m.MAP_IMPORT_MARKER)
    assert c.put('/admin/locations/2', headers=admin, json={**body, 'name': ' '}).status_code == 422
    m.seed_database()
    assert c.get('/locations/2').json()['opening_hours'] == '08:00–20:00'
    assert any(p['id'] == 2 for p in c.get('/search', params={'q': 'quiet room'}).json())


def test_announcement_window_place_filter_and_delete(api_client):
    from datetime import datetime, timedelta, timezone
    c = api_client; admin = login(c, '240000002')
    now = datetime.now(timezone.utc)
    iso = lambda delta: (now + delta).isoformat()
    base = {'title': 'Window test', 'body': 'Sample', 'location_id': 2}
    assert c.post('/admin/announcements', headers=admin, json={**base, 'starts_at': '2030-01-01T10:00:00'}).status_code == 422
    assert c.post('/admin/announcements', headers=admin, json={**base, 'starts_at': iso(timedelta(hours=2)), 'ends_at': iso(timedelta(hours=1))}).status_code == 422
    showing = c.post('/admin/announcements', headers=admin, json={**base, 'title': 'Showing now', 'ends_at': iso(timedelta(hours=1))}).json()
    c.post('/admin/announcements', headers=admin, json={**base, 'title': 'Later', 'starts_at': iso(timedelta(days=1))})
    c.post('/admin/announcements', headers=admin, json={**base, 'title': 'Over', 'starts_at': iso(-timedelta(days=2)), 'ends_at': iso(-timedelta(days=1))})
    public = [n['title'] for n in c.get('/announcements').json()]
    assert 'Showing now' in public and 'Later' not in public and 'Over' not in public
    assert [n['title'] for n in c.get('/announcements', params={'location_id': 2}).json()][0] == 'Showing now'
    assert all(n['location_id'] == 2 for n in c.get('/announcements', params={'location_id': 2}).json())
    states = {n['title']: n['state'] for n in c.get('/admin/announcements', headers=admin).json()}
    assert (states['Showing now'], states['Later'], states['Over']) == ('showing', 'scheduled', 'expired')
    assert c.get('/admin/announcements', headers=login(c)).status_code == 403
    assert c.delete(f"/admin/announcements/{showing['id']}", headers=login(c)).status_code == 403
    assert c.delete(f"/admin/announcements/{showing['id']}", headers=admin).json()['deleted'] is True
    assert 'Showing now' not in [n['title'] for n in c.get('/announcements').json()]
    assert c.delete(f"/admin/announcements/{showing['id']}", headers=admin).status_code == 404


def test_nearby_paths_let_a_place_report_a_blocked_path(api_client):
    c = api_client; visitor = guest(c)
    nearby = c.get(f"/locations/{IDS['red_hall']}/nearby-paths").json()
    assert nearby[0]['label'] == 'Floor 1 corridor between Red Hall and WiFi Zone'
    assert len({frozenset((n['a'], n['b'])) for n in nearby}) == len(nearby) <= 8
    assert 'Block D lift' in [n['label'] for n in c.get(f"/locations/{IDS['lift_block_d']}/nearby-paths").json()]
    assert c.get('/locations/999999999/nearby-paths').json() == []
    report = c.post('/reports', headers=visitor, json={'kind': 'path', 'location_id': IDS['red_hall'], 'message': 'Boxes',
                                                       'edge_a': nearby[0]['a'], 'edge_b': nearby[0]['b']}).json()
    assert report['connection_label'] == nearby[0]['label'] and report['route'] is None


def test_fix_location_resolves_report_and_reporter_sees_unread(api_client):
    c = api_client; student = login(c); admin = login(c, '240000002')
    report = c.post('/reports', headers=student, json={'kind': 'location', 'location_id': 2, 'message': 'Open until 22:00'}).json()
    other = c.post('/reports', headers=student, json={'kind': 'location', 'location_id': 1, 'message': 'Other place'}).json()
    library = c.get('/locations/2').json()
    assert c.put('/admin/locations/2', headers=admin, json={**library, 'report_id': other['id']}).status_code == 404
    c.put('/admin/locations/2', headers=admin, json={**library, 'opening_hours': '08:00–22:00', 'report_id': report['id']})
    mine = {r['id']: r for r in c.get('/reports/me', headers=student).json()}
    assert mine[report['id']]['status'] == 'resolved' and mine[report['id']]['reporter_unread'] is True
    assert 'We updated the details for' in mine[report['id']]['resolution_note']
    assert mine[other['id']]['reporter_unread'] is False
    assert c.post('/reports/me/seen', headers=student).json()['seen'] == 1
    assert not any(r['reporter_unread'] for r in c.get('/reports/me', headers=student).json())
    c.put(f"/admin/reports/{other['id']}", headers=admin, json={'status': 'new', 'resolution_note': ''})
    assert c.get('/reports/me', headers=student).json()[-1]['reporter_unread'] is False


def test_withdraw_only_own_open_reports(api_client):
    c = api_client; student = login(c); admin = login(c, '240000002')
    report = c.post('/reports', headers=student, json={'kind': 'location', 'location_id': 2, 'message': 'Mistake'}).json()
    assert c.post(f"/reports/{report['id']}/withdraw", headers=login(c, '240103050')).status_code == 404
    assert c.post(f"/reports/{report['id']}/withdraw", headers=student).json()['status'] == 'withdrawn'
    assert c.post(f"/reports/{report['id']}/withdraw", headers=student).status_code == 409
    assert c.get('/admin/reports', headers=admin).json()[0]['status'] == 'withdrawn'


def test_duplicate_path_reports_grouped_and_resolved_together(api_client):
    c = api_client; a = login(c); b = login(c, '240103050'); admin = login(c, '240000002')
    part = c.get(f"/locations/{IDS['red_hall']}/nearby-paths").json()[0]
    assert part['floor'] == part['to_floor'] == 1
    body = {'kind': 'path', 'message': 'Blocked', 'edge_a': part['a'], 'edge_b': part['b']}
    first = c.post('/reports', headers=a, json=body).json()
    second = c.post('/reports', headers=b, json={**body, 'edge_a': part['b'], 'edge_b': part['a']}).json()
    states = c.get('/paths/status').json()
    assert states == [{'a': min(part['a'], part['b']), 'b': max(part['a'], part['b']), 'state': None, 'open_reports': 2}]
    listed = {r['id']: r for r in c.get('/admin/reports', headers=admin).json()}
    assert listed[first['id']]['similar_open'] == [second['id']]
    c.post('/admin/path-status', headers=admin, json={'edge_a': part['a'], 'edge_b': part['b'], 'state': 'closed', 'report_id': first['id']})
    for headers in (a, b):
        mine = c.get('/reports/me', headers=headers).json()[0]
        assert mine['status'] == 'resolved' and mine['reporter_unread'] is True and 'routes go around it' in mine['resolution_note']
    assert c.post('/reports', headers=a, json=body).status_code == 409
    assert c.get('/paths/status').json()[0]['state'] == 'closed'


def test_timed_closure_reopens_by_itself_and_routes_say_why(api_client):
    from datetime import datetime, timedelta, timezone
    from sqlmodel import Session
    c = api_client; admin = login(c, '240000002')
    route = c.get('/routes', params={'destination': IDS['d201']}).json()
    part = next(x for x in route['connections'] if m.draft_route(m.CAMPUS_MAP, 1, IDS['d201'], False,
                {m.edge_key(x['a'], x['b']): 'closed'})['status'] == 'schematic_draft')
    body = {'edge_a': part['a'], 'edge_b': part['b'], 'state': 'closed'}
    assert c.post('/admin/path-status', headers=admin, json={**body, 'reopens_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}).status_code == 422
    closure = c.post('/admin/path-status', headers=admin, json={**body, 'reopens_at': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}).json()
    detour = c.get('/routes', params={'destination': IDS['d201']}).json()
    assert f"Goes around a closed path: {part['label']}." in detour['warnings']
    with Session(m.engine) as db:
        row = db.get(m.PathStatus, closure['id'])
        row.reopens_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(row); db.commit()
    assert c.get('/routes', params={'destination': IDS['d201']}).json()['connections'] == route['connections']
    assert c.get('/admin/path-status', headers=admin).json() == []


def test_guest_reports_move_to_account_on_sign_in(api_client):
    c = api_client
    token = c.post('/auth/guest').json()['access_token']
    report = c.post('/reports', headers={'Authorization': 'Bearer ' + token},
                    json={'kind': 'location', 'location_id': 2, 'message': 'Guest report'}).json()
    signed_in = c.post('/auth/login', json={'sdu_id': '240103053', 'password': 'Campus123!'}).json()
    mine = c.get('/reports/me', headers={'Authorization': 'Bearer ' + signed_in['access_token']}).json()
    assert [r['id'] for r in mine] == [report['id']]
