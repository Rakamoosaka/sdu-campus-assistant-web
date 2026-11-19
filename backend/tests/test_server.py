from fastapi.testclient import TestClient
from app import server


def test_one_address_serves_site_and_api(tmp_path, monkeypatch):
    dist = tmp_path / 'dist'
    (dist / 'assets').mkdir(parents=True)
    (dist / 'index.html').write_text('<div id="root">site</div>')
    (dist / 'assets' / 'app.js').write_text('console.log(1)')
    (tmp_path / 'secret.txt').write_text('outside the site')
    monkeypatch.setattr(server, 'WEB_DIST', dist.resolve())
    with TestClient(server.site) as c:
        assert c.get('/api/health').json()['status'] == 'ok'
        for page in ['/', '/map', '/reports', '/admin']:
            response = c.get(page)
            assert response.text == '<div id="root">site</div>' and response.headers['cache-control'] == 'no-cache'
        asset = c.get('/assets/app.js')
        assert asset.text == 'console.log(1)' and 'immutable' in asset.headers['cache-control']
        assert 'outside the site' not in c.get('/%2e%2e/secret.txt').text
        same_site = c.post('/api/auth/login', headers={'Origin': 'http://testserver'},
                           json={'sdu_id': '240103049', 'password': 'Campus123!'})
        assert same_site.status_code == 200
        assert c.get('/api/users/me').headers['cache-control'] == 'no-store'
        assert c.post('/api/auth/login', headers={'Origin': 'https://evil.example'},
                      json={'sdu_id': '240103049', 'password': 'Campus123!'}).status_code == 403
