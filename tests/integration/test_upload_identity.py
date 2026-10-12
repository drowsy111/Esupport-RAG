import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Document, DocumentVersion, UploadClaim, UploadReceipt
from tests.conftest import authenticate, upload


def test_identical_upload_reuses_file_job_and_vectors(environment):
    env = environment
    headers = authenticate(env)
    first = upload(env, headers).json()
    vectors = len(env.resources.vectors.rows)
    second = upload(env, headers)
    assert second.status_code == 202
    assert second.json()['reused'] is True
    assert second.json()['job_id'] == first['job_id']
    assert len(env.resources.storage.objects) == 1
    assert len(env.resources.vectors.rows) == vectors
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 1


def test_idempotency_replay_and_changed_payload_conflict(environment):
    env = environment
    headers = {**authenticate(env), 'Idempotency-Key': 'upload-001'}
    first = upload(env, headers).json()
    second = upload(env, headers).json()
    assert second['replayed'] is True
    assert second['version_id'] == first['version_id']
    conflict = upload(env, headers, text='# Changed')
    assert conflict.status_code == 409
    assert conflict.json()['code'] == 'IDEMPOTENCY_CONFLICT'
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(UploadReceipt)) == 1


def test_renamed_content_reuses_but_changed_name_content_needs_choice(environment):
    env = environment
    headers = authenticate(env)
    first = upload(env, headers).json()
    renamed = env.client.post('/api/v1/documents/upload', headers=headers,
        data={'knowledge_base_id': env.ids['a_kb']},
        files={'file': ('renamed.md', b'# Support\n\nCheck network DEMO-001.', 'text/markdown')})
    assert renamed.json()['document_id'] == first['document_id']
    conflict = upload(env, headers, text='# Different')
    assert conflict.status_code == 409
    separate = upload(env, headers, text='# Different', allow_same_name='true')
    assert separate.status_code == 202
    assert separate.json()['document_id'] != first['document_id']


def test_new_version_failure_preserves_old_then_retry_switches(environment):
    env = environment
    headers = authenticate(env)
    first = upload(env, headers).json()
    env.resources.vectors.fail_next = True
    updated = upload(env, headers, text='# New\n\nNew network instructions.',
                     document_id=first['document_id']).json()
    assert updated['status'] == 'FAILED'
    assert updated['revision'] == 2
    assert updated['document_id'] == first['document_id']
    def search():
        return env.client.post('/api/v1/search', headers=headers,
                               json={'query': 'network'}).json()['candidates']
    assert {c['version_id'] for c in search()} == {first['version_id']}
    repeated = upload(env, headers, text='# New\n\nNew network instructions.',
                      document_id=first['document_id']).json()
    assert repeated['job_id'] == updated['job_id']
    assert repeated['status'] == 'FAILED'
    blocked = upload(env, headers, text='# Third', document_id=first['document_id'])
    assert blocked.status_code == 409
    retry = env.client.post(f"/api/v1/jobs/{updated['job_id']}/retry", headers=headers)
    assert retry.status_code == 202
    assert {c['version_id'] for c in search()} == {updated['version_id']}
    with env.factory() as session:
        assert session.get(DocumentVersion, first['version_id']).publication_status == 'SUPERSEDED'


def test_same_file_different_tenants_and_metadata_are_independent(environment):
    env = environment
    a = upload(env, authenticate(env)).json()
    b = upload(env, authenticate(env, 'b'), suffix='b').json()
    assert a['document_id'] != b['document_id']
    other = upload(env, authenticate(env), product_version='2.0', allow_same_name='true').json()
    assert other['document_id'] != a['document_id']
    forbidden = upload(env, authenticate(env, 'b'), suffix='b', document_id=a['document_id'])
    assert forbidden.status_code == 404


def test_queued_upload_returns_existing_task(environment):
    env = environment
    dispatched = []
    env.resources.dispatch = dispatched.append
    headers = authenticate(env)
    first = upload(env, headers).json()
    second = upload(env, headers).json()
    assert second['status'] == 'QUEUED'
    assert first['job_id'] == second['job_id']
    assert dispatched == [first['job_id']]


def test_legacy_upload_without_claim_is_reused(environment):
    env = environment
    headers = authenticate(env)
    first = upload(env, headers).json()
    with env.factory() as session:
        session.execute(delete(UploadClaim))
        session.commit()
    assert upload(env, headers).json()['version_id'] == first['version_id']


def test_database_rejects_duplicate_claim_and_receipt(environment):
    env = environment
    first = upload(env, {**authenticate(env), 'Idempotency-Key': 'unique'}).json()
    with env.factory() as session:
        claim_key = session.scalar(select(UploadClaim.key))
        receipt_key = session.scalar(select(UploadReceipt.key))
        for duplicate in (UploadClaim(key=claim_key, version_id=first['version_id']),
                          UploadReceipt(key=receipt_key, fingerprint='x' * 64,
                                        version_id=first['version_id'])):
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
