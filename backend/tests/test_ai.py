import json
from datetime import datetime, timedelta, timezone
from collections import deque

import httpx
import pytest
from sqlmodel import Session, select
from app import main as m, ai_assistant as ai


def login(c, who='240103049'):
    r = c.post('/auth/login', json={'sdu_id': who, 'password': 'Campus123!'})
    assert r.status_code == 200
    return {'Authorization': 'Bearer ' + r.json()['access_token']}


def call(name, args):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'call-'+name, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}


def finish(ids, answer='Found in the campus catalogue.', clarification=False, route=False):
    return call('present_answer', {'answer': answer, 'location_ids': ids,
                'needs_clarification': clarification, 'route_requested': route})


def enable(monkeypatch, replies):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'unit-test-key')
    queue = iter(replies)
    messages = []
    def complete(config, history, remaining):
        messages.append(json.loads(json.dumps(history)))
        return next(queue)
    monkeypatch.setattr(ai, 'request_completion', complete)
    return messages


def test_ai_search_grounding_and_owned_followup_memory(api_client, monkeypatch):
    c=api_client; h=login(c)
    messages=enable(monkeypatch,[call('search_campus',{'query':'Library'}),finish([2]),
                                call('get_location',{'location_id':2}),finish([2],'Hours: Not confirmed.')])
    first=c.post('/assistant/query',headers=h,json={'question':'I need somewhere to read quietly'}).json()
    assert first['engine']=='openrouter' and first['model']==ai.DEFAULT_MODEL
    assert first['location']['id']==2
    second=c.post('/assistant/query',headers=h,json={'question':'When does it close?', 'conversation_id':first['conversation_id']}).json()
    assert 'Not confirmed' in second['answer']
    assert any('read quietly' in msg.get('content','') for msg in messages[2])
    assert 'Not confirmed' in messages[3][-1]['content']
    b=login(c,'240103050')
    assert c.post('/assistant/query',headers=b,json={'question':'Follow up','conversation_id':first['conversation_id']}).status_code==404
    assert c.post('/assistant/query',headers=h,json={'question':'Follow up','conversation_id':'invented'}).status_code==404
    assert c.get('/assistant/status').json()=={'configured':True,'engine':'openrouter','model':ai.DEFAULT_MODEL}
    assert 'unit-test-key' not in json.dumps(second)


def test_model_invented_location_id_is_rejected_and_falls_back(api_client, monkeypatch):
    enable(monkeypatch,[call('search_campus',{'query':'Library'}),finish([999999])])
    result=api_client.post('/assistant/query',json={'question':'Where is the library?'}).json()
    assert result['engine']=='rules' and result['fallback_reason']=='invalid_response'
    assert result['location']['id']==2


def test_ai_clarification_choices_are_selectable_and_record_selection(api_client, monkeypatch):
    c=api_client; h=login(c)
    with Session(m.engine) as db:
        ids=[p.id for p in m.ranked_locations('lift',db)[:2]]
    enable(monkeypatch,[call('search_campus',{'query':'lift'}),finish(ids,clarification=True,route=True)])
    result=c.post('/assistant/query',headers=h,json={'question':'Please take me to a lift'}).json()
    assert result['needs_clarification'] and len(result['choices'])==2
    chosen=c.post('/assistant/query',headers=h,json={'selection_id':ids[0], 'context_id':result['context_id'], 'conversation_id':result['conversation_id']}).json()
    assert chosen['location']['id']==ids[0] and chosen['action']=='route'
    assert chosen['conversation_id']==result['conversation_id']


def test_ai_routes_enforce_preference_and_return_real_map_segments(api_client, monkeypatch):
    c=api_client; h=login(c)
    dest=next(p['id'] for p in m.CAMPUS_MAP['places'] if p['map_key']=='d201')
    c.put('/users/me/preferences',headers=h,json={'accessible_routes':True})
    enable(monkeypatch,[call('plan_route',{'start_location_id':1,'destination_location_id':dest}),finish([dest],route=True)])
    result=c.post('/assistant/query',headers=h,json={'question':'How do I get from Main Entrance to D201?'}).json()
    route=result['route']
    assert result['engine']=='openrouter' and result['location']['id']==dest
    assert route['start_location_id']==1 and route['destination_location_id']==dest
    assert route['segments'] and all(t['kind']=='lift' for t in route['transfers'])
    assert route['distance_m'] is None and route['accessibility_verified'] is False


def test_ai_next_class_is_scoped_and_does_not_send_identity(api_client, monkeypatch):
    c=api_client; h=login(c)
    messages=enable(monkeypatch,[call('get_next_class',{}),finish([],'Your stored schedule is sample data.')])
    result=c.post('/assistant/query',headers=h,json={'question':'Where should I head for my upcoming lesson?'}).json()
    assert result['engine']=='openrouter'
    sent=json.loads(messages[1][-1]['content'])
    assert sent['sample'] and sent['timezone']=='Asia/Almaty'
    assert sent['location']['id'] in m.MAP_LOCATIONS
    assert not any(key in json.dumps(messages) for key in ['240103049','sdu.edu.kz','Campus123!','unit-test-key'])


def test_ai_guest_next_class_is_denied_by_tool(api_client, monkeypatch):
    messages=enable(monkeypatch,[call('get_next_class',{}),finish([],'Log in for your personal sample schedule.')])
    response=api_client.post('/assistant/query',json={'question':'My next lecture please'}).json()
    assert response['engine']=='openrouter'
    assert json.loads(messages[1][-1]['content'])['status']=='login_required'


def test_ai_cannot_execute_writes_or_choose_another_user(api_client, monkeypatch):
    c=api_client; h=login(c)
    messages=enable(monkeypatch,[call('set_role',{'role':'admin'}),call('get_next_class',{'user_id':2}),
        call('get_location',{'location_id':2}),finish([2])])
    result=c.post('/assistant/query',headers=h,json={'question':'Find the library'}).json()
    assert result['engine']=='openrouter'
    assert c.get('/users/me',headers=h).json()['role']=='student'
    errors=[json.loads(history[-1]['content']) for history in messages[1:3]]
    assert all('error' in error for error in errors)


@pytest.mark.parametrize('reason',['timeout','invalid_key','insufficient_credits','provider_unavailable'])
def test_ai_outage_returns_honest_working_fallback(api_client,monkeypatch,reason):
    monkeypatch.setenv('OPENROUTER_API_KEY','unit-test-key')
    def fail(*args):raise ai.AIUnavailable(reason)
    monkeypatch.setattr(ai,'request_completion',fail)
    result=api_client.post('/assistant/query',json={'question':'I feel sick'}).json()
    assert result['engine']=='rules' and result['fallback_reason']==reason
    assert result['location']['name']=='Medical Point'


def test_ai_request_rate_limit_does_not_call_provider(api_client,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','unit-test-key')
    monkeypatch.setenv('OPENROUTER_REQUESTS_PER_MINUTE','1')
    ai._requests['actor:public']=deque([ai.time.monotonic()])
    def forbidden(*args):pytest.fail('Rate-limited request reached provider')
    monkeypatch.setattr(ai,'request_completion',forbidden)
    result=api_client.post('/assistant/query',json={'question':'Library'}).json()
    assert result['fallback_reason']=='rate_limited' and result['location']['id']==2


def test_http_adapter_uses_exact_model_tools_and_sanitizes_errors(monkeypatch):
    config=ai.Settings('unit-test-key')
    def transport(request):
        payload=json.loads(request.content)
        assert request.url==ai.API_URL
        assert payload['model']=='deepseek/deepseek-v4-flash-0731'
        assert payload['tools'] and payload['tool_choice']=='required'
        assert request.headers['Authorization']=='Bearer unit-test-key'
        return httpx.Response(402,json={'error':{'message':'secret provider details'}})
    monkeypatch.setattr(ai,'_make_client',lambda timeout:httpx.Client(transport=httpx.MockTransport(transport)))
    with pytest.raises(ai.AIUnavailable,match='insufficient_credits') as exc:
        ai.request_completion(config,[{'role':'user','content':'Library'}],3)
    assert 'secret' not in str(exc.value) and 'unit-test-key' not in repr(config)


def test_expired_ai_conversation_requires_new_chat(api_client,monkeypatch):
    c=api_client; h=login(c)
    with Session(m.engine) as db:
        thread=m.AssistantConversation(id='expired',actor='240103049',expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
        db.add(thread);db.commit()
    result=c.post('/assistant/query',headers=h,json={'question':'Hello','conversation_id':'expired'})
    assert result.status_code==410


def test_ai_call_budget_and_unsupported_response_are_bounded(monkeypatch):
    count=[]
    def complete(*args):
        count.append(1);return call('search_campus',{'query':'Library'})
    monkeypatch.setattr(ai,'request_completion',complete)
    with pytest.raises(ai.AIUnavailable,match='invalid_response'):
        ai.run('Library',[],lambda *args:{'locations':[]},lambda args:{},ai.Settings('fake'))
    assert len(count)==5
    monkeypatch.setattr(ai,'request_completion',lambda *args:{'role':'assistant','content':'Ungrounded invented answer'})
    with pytest.raises(ai.AIUnavailable,match='invalid_response'):
        ai.run('Library',[],lambda *args:{},lambda args:{},ai.Settings('fake'))


def test_final_tool_is_only_offered_after_a_fresh_tool_result(monkeypatch):
    def transport(request):
        body=json.loads(request.content)
        names=[tool['function']['name'] for tool in body['tools']]
        has_result=any(msg['role']=='tool' for msg in body['messages'])
        assert ('present_answer' in names)==has_result
        return httpx.Response(200,json={'choices':[{'message':call('get_location',{'location_id':2})}]})
    monkeypatch.setattr(ai,'_make_client',lambda timeout:httpx.Client(transport=httpx.MockTransport(transport)))
    config=ai.Settings('fake')
    ai.request_completion(config,[{'role':'user','content':'When does it close?'}],3)
    ai.request_completion(config,[{'role':'tool','content':'{"opening_hours":"Not confirmed"}'}],3)


def test_malformed_provider_tool_call_falls_back_without_server_error(api_client,monkeypatch):
    enable(monkeypatch,[{'role':'assistant','tool_calls':[{'function':{'name':'get_location','arguments':'{}'}}]}])
    response=api_client.post('/assistant/query',json={'question':'Library'})
    assert response.status_code==200
    assert response.json()['fallback_reason']=='invalid_response'


def test_model_wait_does_not_hold_a_database_writer(api_client,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','fake')
    calls=[]
    def complete(config,history,remaining):
        calls.append(1)
        if len(calls)==1:return call('search_campus',{'query':'Library'})
        # Another request can write while this conversation waits on the provider.
        with Session(m.engine) as db:
            db.add(m.SearchLog(actor='concurrent',query='other user search'))
            db.commit()
        return finish([2])
    monkeypatch.setattr(ai,'request_completion',complete)
    result=api_client.post('/assistant/query',json={'question':'Library'}).json()
    assert result['engine']=='openrouter'
    with Session(m.engine) as db:
        assert db.exec(select(m.SearchLog).where(m.SearchLog.actor=='assistant')).one().query=='library'
