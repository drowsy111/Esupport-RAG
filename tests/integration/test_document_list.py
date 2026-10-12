from tests.conftest import authenticate, upload


def test_list_is_scoped_paginated_and_reports_job(environment):
    env = environment
    headers = authenticate(env)
    first = upload(env, headers).json()
    upload(env, headers, text="# Other", allow_same_name="true")
    response = env.client.get('/api/v1/documents', headers=headers,
        params={'knowledge_base_id': env.ids['a_kb'], 'page_size': 1})
    assert response.status_code == 200
    assert response.json()['total'] == 2
    assert len(response.json()['items']) == 1
    all_rows = env.client.get('/api/v1/documents', headers=headers,
        params={'knowledge_base_id': env.ids['a_kb']}).json()['items']
    row = next(r for r in all_rows if r['id'] == first['document_id'])
    assert row['job_id'] == first['job_id']
    assert row['published_version_id'] == first['version_id']
    denied = env.client.get('/api/v1/documents', headers=authenticate(env, 'b'),
        params={'knowledge_base_id': env.ids['a_kb']})
    assert denied.status_code == 404
    member = env.client.get('/api/v1/documents', headers=authenticate(env, username='member'),
        params={'knowledge_base_id': env.ids['a_kb']})
    assert member.status_code == 200


def test_list_requires_login_and_valid_pagination(environment):
    env = environment
    assert env.client.get('/api/v1/documents', params={
        'knowledge_base_id': env.ids['a_kb']}).status_code == 401
    assert env.client.get('/api/v1/documents', headers=authenticate(env), params={
        'knowledge_base_id': env.ids['a_kb'], 'page_size': 101}).status_code == 422
