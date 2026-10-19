from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app import main as m


def login(client, who='240103049'):
    result=client.post('/auth/login',json={'sdu_id':who,'password':'Campus123!'})
    assert result.status_code==200
    return {'Authorization':'Bearer '+result.json()['access_token']}


def test_cookie_session_csrf_logout_and_replay(api_client):
    c=api_client
    result=c.post('/auth/login',json={'sdu_id':'240103049','password':'Campus123!'})
    cookie=result.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    token=result.json()['access_token']
    csrf=c.get('/auth/csrf').json()['csrf_token']
    assert c.get('/users/me').json()['full_name']=='Yerassyl'
    assert c.put('/users/me/preferences',json={'accessible_routes':True}).status_code==403
    assert c.put('/users/me/preferences',headers={'X-CSRF-Token':csrf},json={'accessible_routes':True}).status_code==200
    assert c.post('/auth/logout',headers={'X-CSRF-Token':csrf}).status_code==200
    assert c.get('/users/me').status_code==401
    assert c.get('/users/me',headers={'Authorization':'Bearer '+token}).status_code==401


def test_invalid_duplicate_and_no_registration_admin(api_client):
    c=api_client
    for bad in ['123','abc123456','１２３４５６７８９']:
        assert c.post('/auth/register',json={'sdu_id':bad,'full_name':'New Person','password':'Campus123!'}).status_code==422
    body={'sdu_id':'299999991','full_name':'New Person','password':'Campus123!','role':'admin'}
    r=c.post('/auth/register',json=body)
    assert r.status_code==201 and r.json()['role']=='student'
    assert c.post('/auth/register',json=body).status_code==409
    assert c.post('/auth/login',json={'sdu_id':body['sdu_id'],'password':'wrong password'}).status_code==401
    assert c.post('/auth/register',json={**body,'sdu_id':'299999992','password':'short'}).status_code==422


def test_guest_restrictions_and_public_endpoints(api_client):
    c=api_client
    r=c.post('/auth/guest'); headers={'Authorization':'Bearer '+r.json()['access_token']}
    for path in ['/users/me/favorites','/users/me/preferences','/students/me/timetable','/teachers/me/schedule','/reports/me','/admin/users']:
        assert c.get(path,headers=headers).status_code==403,path
    assert c.post('/users/me/favorites/2',headers=headers).status_code==403
    assert c.delete('/users/me/favorites/2',headers=headers).status_code==403
    assert c.post('/reports',headers=headers,json={'message':'Report'}).status_code==403
    for path in ['/locations','/campus-map','/routes?destination=2','/search?q=D201','/announcements']:
        assert c.get(path).status_code==200


def test_user_isolation_and_current_role_authorization(api_client):
    c=api_client; a=login(c); b=login(c,'240103050')
    assert c.post('/users/me/favorites/2',headers=a).status_code==201
    assert c.get('/users/me/favorites',headers=b).json()==[]
    assert c.put('/users/me/preferences',headers=a,json={'accessible_routes':True}).status_code==200
    assert c.get('/users/me/preferences',headers=b).json()['accessible_routes'] is False
    assert c.get('/admin/users',headers=a).status_code==403
    admin=login(c,'240000002')
    user=c.get('/users/me',headers=a).json()
    assert c.put(f"/admin/users/{user['id']}/roles",headers=admin,json={'role':'teacher'}).status_code==200
    assert c.get('/users/me',headers=a).json()['role']=='teacher'
    assert c.put(f"/admin/users/{user['id']}/roles",headers=admin,json={'role':'student'}).status_code==200
    # Startup must never overwrite an administrator's role edits.
    m.seed_database()
    assert c.get('/users/me',headers=a).json()['role']=='student'


def test_normalized_alias_typo_search_and_real_analytics(api_client):
    c=api_client; admin=login(c,'240000002')
    assert c.get('/admin/analytics/popular-searches',headers=admin).json()==[]
    for query,name in [('D201','D201'),('d 201','D201'),('libary','Library'),('first aid','Medical Point')]:
        results=c.get('/search',params={'q':query}).json()
        assert results[0]['name']==name,(query,results)
    assert c.get('/search?q=zzzznonexistentzzzz').json()==[]
    stats=c.get('/admin/analytics/popular-searches',headers=admin).json()
    assert sum(row['count'] for row in stats)==5
    assert {row['query'] for row in stats}=={'d201','d 201','libary','first aid','zzzznonexistentzzzz'}


def test_assistant_recommendations_and_missing_facts(api_client):
    c=api_client
    for question,name in [('I feel sick','Medical Point'),('Where can I print?','Print & Stationery'),('Where will I print documents?','Print & Stationery'),('Can you tell me where d 201 is?','D201'),('I need a place to study','Library'),('Where is d 201?','D201')]:
        result=c.post('/assistant/query',json={'question':question}).json()
        assert result['location']['name']==name,result
    result=c.post('/assistant/query',json={'question':'What are the library opening hours?'}).json()
    assert 'Not confirmed' in result['answer']
    assert c.post('/assistant/query',json={'question':'Where can I park?'}).json()['location'] is None
    assert c.post('/assistant/query',json={'question':'a moon elevator'}).json()['location'] is None
    assert 'Log in' in c.post('/assistant/query',json={'question':'my next lesson'}).json()['answer']


def test_clarification_choices_context_and_ownership(api_client):
    c=api_client; a=login(c)
    result=c.post('/assistant/query',headers=a,json={'question':'directions to a lift'}).json()
    assert result['needs_clarification'] and len(result['choices'])>1
    selected=result['choices'][0]['id']
    selection={'context_id':result['context_id'],'selection_id':selected}
    resolved=c.post('/assistant/query',headers=a,json=selection).json()
    assert resolved['location']['id']==selected and resolved['action']=='route'
    b=login(c,'240103050')
    assert c.post('/assistant/query',headers=b,json=selection).status_code==422
    assert c.post('/assistant/query',headers=a,json={**selection,'selection_id':999}).status_code==422


def test_next_class_real_dates_timezone_empty_and_unmapped(api_client):
    c=api_client; headers=login(c)
    me=c.get('/users/me',headers=headers).json()
    identity={'sub':me['sdu_id'],'role':'student'}
    with Session(m.engine) as db:
        for lesson in db.exec(select(m.SampleLesson).where(m.SampleLesson.user_id==me['id'])).all():db.delete(lesson)
        now=datetime(2026,10,19,23,40,tzinfo=m.TZ)
        mapped=next(p for p in m.MAP_LOCATIONS.values() if p['name']=='D201')
        db.add_all([
            m.SampleLesson(user_id=me['id'],course='Past',room='D201',starts_at=now-timedelta(minutes=1),location_id=mapped['id']),
            m.SampleLesson(user_id=me['id'],course='Tomorrow',room='Unknown',starts_at=now+timedelta(minutes=30),location_id=None),
            m.SampleLesson(user_id=me['id'],course='Later',room='D201',starts_at=now+timedelta(days=1),location_id=mapped['id'])])
        db.commit()
        lesson=m.upcoming_lesson(identity,db,now)
        assert lesson.course=='Tomorrow'
        assert m.as_utc(lesson.starts_at).astimezone(m.TZ).day==20
        assert m.upcoming_lesson(identity,db,now+timedelta(days=2)) is None
    response=c.get('/students/me/timetable',headers=headers)
    assert len(response.json())==3 and all(x['sample'] for x in response.json())
    new=c.post('/auth/register',json={'sdu_id':'299999993','full_name':'Empty Schedule','password':'Campus123!'}).json()
    h={'Authorization':'Bearer '+new['access_token']}
    assert c.get('/students/me/next-class',headers=h).json() is None
    assert c.get('/students/me/timetable',headers=h).json()==[]
    assert 'no upcoming lessons' in c.post('/assistant/query',headers=h,json={'question':'my next class'}).json()['answer']


def test_saved_preference_drives_routes_and_unavailable_canteen(api_client):
    c=api_client; h=login(c); ids={p['map_key']:p['id'] for p in m.CAMPUS_MAP['places']}
    assert c.put('/users/me/preferences',headers=h,json={'accessible_routes':True}).status_code==200
    path=c.get('/routes',headers=h,params={'destination':ids['d201'],'accessible':False}).json()
    assert path['avoid_stairs'] is True
    assert all(t['kind']=='lift' for t in path['transfers'])
    assert c.get('/routes',headers=h,params={'destination':ids['canteen_floor_3']}).json()['status']=='no_route'
    assert c.get('/routes?destination=999999999',headers=h).json()['status']=='unmapped'


def test_s6_skip_s1_absent_disconnected_and_restricted():
    import copy
    campus=copy.deepcopy(m.CAMPUS_MAP)
    places={p['map_key']:p for p in campus['places']}
    assert 'stair_main_01' not in places
    assert all('stair_main_01' not in str(e) for e in campus['routing']['edges'])
    s6=[e for e in campus['routing']['edges'] if e.get('label') and '6' in e['label'] and e['kind']=='stairs']
    assert s6 and all({campus['routing']['node_floors'][e['a']],campus['routing']['node_floors'][e['b']]}=={1,3} for e in s6)
    places['d201']['access']='restricted'
    assert m.draft_route(campus,1,places['d201']['id'])['status']=='restricted'
    places['d201']['access']='public';campus['routing']['edges']=[]
    assert m.draft_route(campus,1,places['d201']['id'])['status']=='no_route'


def test_admin_edits_announcements_report_status_and_persistence(api_client):
    c=api_client; student=login(c); admin=login(c,'240000002')
    location=c.get('/locations/2').json();location.update(opening_hours='Sample test hours',contact='Not confirmed')
    assert c.put('/admin/locations/2',headers=student,json=location).status_code==403
    assert c.put('/admin/locations/2',headers=admin,json=location).status_code==200
    m.seed_database()
    assert c.get('/locations/2').json()['opening_hours']=='Sample test hours'
    report=c.post('/reports',headers=student,json={'message':'Please check these hours','location_id':2}).json()
    assert report['location_id']==2
    assert c.put(f"/admin/reports/{report['id']}",headers=admin,json={'status':'resolved'}).json()['status']=='resolved'
    assert c.get('/reports/me',headers=student).json()[0]['status']=='resolved'
    assert c.put(f"/admin/reports/{report['id']}",headers=admin,json={'status':'invalid'}).status_code==422
    news={'title':'Sample event','body':'Sample event details','location_id':2}
    result=c.post('/admin/announcements',headers=admin,json=news)
    assert result.status_code==201
    news['title']='Edited sample event'
    assert c.put(f"/admin/announcements/{result.json()['id']}",headers=admin,json=news).status_code==200
    assert any(row['title']==news['title'] for row in c.get('/announcements').json())
    assert c.post('/reports',headers=student,json={'message':'x','location_id':999999}).status_code==404


def test_cors_and_login_origin(api_client):
    c=api_client
    assert c.post('/auth/login',headers={'Origin':'https://evil.example'},json={'sdu_id':'240103049','password':'Campus123!'}).status_code==403
    result=c.options('/auth/login',headers={'Origin':'http://127.0.0.1:5173','Access-Control-Request-Method':'POST'})
    assert result.headers['access-control-allow-origin']=='http://127.0.0.1:5173'


def test_schedule_edits_persist_and_cannot_edit_another_users_lesson(api_client):
    c=api_client; a=login(c); b=login(c,'240103050')
    body={'course':'User sample lesson','room':'D201','location_id':next(p['id'] for p in m.MAP_LOCATIONS.values() if p['map_key']=='d201'),'starts_at':'2030-01-15T10:30:00+05:00'}
    response=c.post('/students/me/timetable',headers=a,json=body)
    assert response.status_code==201
    lesson=response.json();assert lesson['starts_at'].startswith('2030-01-15T05:30:00')
    body['course']='Edited lesson'
    assert c.put(f"/students/me/timetable/{lesson['id']}",headers=b,json=body).status_code==404
    assert c.put(f"/students/me/timetable/{lesson['id']}",headers=a,json=body).json()['course']=='Edited lesson'
    assert any(x['course']=='Edited lesson' for x in c.get('/students/me/timetable',headers=a).json())
    assert c.post('/students/me/timetable',headers=a,json={**body,'starts_at':'2030-01-15T10:30:00'}).status_code==422


def test_historical_saves_are_not_truncated_and_duplicates_do_not_take_slots(api_client):
    c=api_client; h=login(c); user=c.get('/users/me',headers=h).json()
    ids=[p['id'] for p in m.CAMPUS_MAP['places'][:7]]
    with Session(m.engine) as db:
        for location_id in [*ids[:4],ids[0]]:
            db.add(m.Favorite(user_id=user['id'],location_id=location_id))
        db.commit()
    assert c.post(f'/users/me/favorites/{ids[4]}',headers=h).status_code==201
    with Session(m.engine) as db:
        db.add(m.Favorite(user_id=user['id'],location_id=ids[5]));db.commit()
    m.seed_database()
    assert len(c.get('/users/me/favorites',headers=h).json())==6
    assert c.post(f'/users/me/favorites/{ids[6]}',headers=h).status_code==409
    assert c.delete(f'/users/me/favorites/{ids[0]}',headers=h).status_code==200
    assert len(c.get('/users/me/favorites',headers=h).json())==5
    assert c.delete(f'/users/me/favorites/{ids[1]}',headers=h).status_code==200
    assert c.post(f'/users/me/favorites/{ids[6]}',headers=h).status_code==201


def test_expired_browser_session_and_password_hash_survive_seed(api_client):
    c=api_client; h=login(c)
    import jwt
    token=jwt.decode(h['Authorization'][7:],m.JWT_SECRET,algorithms=['HS256'])
    with Session(m.engine) as db:
        account=db.exec(select(m.AuthAccount).where(m.AuthAccount.sdu_id=='240103049')).one()
        encoded=account.password_hash
        record=db.get(m.BrowserSession,token['jti']);record.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.add(record);db.commit()
    assert c.get('/users/me',headers=h).status_code==401
    m.seed_database()
    with Session(m.engine) as db:
        assert db.exec(select(m.AuthAccount).where(m.AuthAccount.sdu_id=='240103049')).one().password_hash==encoded


def test_swagger_auth_contract_and_same_origin_login(api_client):
    c=api_client
    assert c.get('/docs').status_code==200
    schema=c.get('/openapi.json').json()
    assert 'HTTPBearer' in schema['components']['securitySchemes']
    assert schema['paths']['/users/me']['get']['security']
    result=c.post('/auth/login',headers={'Origin':'http://testserver'},json={'sdu_id':'240103049','password':'Campus123!'})
    assert result.status_code==200
    h={'Authorization':'Bearer '+result.json()['access_token'],'Origin':'http://testserver'}
    assert c.put('/users/me/preferences',headers=h,json={'accessible_routes':True}).status_code==200


def test_concurrent_saves_never_exceed_five(api_client):
    from concurrent.futures import ThreadPoolExecutor
    c=api_client; h=login(c)
    ids=[p['id'] for p in m.CAMPUS_MAP['places'][:8]]
    def save(location_id):
        return c.post(f'/users/me/favorites/{location_id}',headers=h).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses=list(pool.map(save,ids))
    assert statuses.count(201)==5
    assert statuses.count(409)==3
    assert len(c.get('/users/me/favorites',headers=h).json())==5
