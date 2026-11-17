"""Synthetic human decisions and frozen files; no provider/reference/live storage."""

from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlmodel import Session, select

from app.core.db import engine
from app.main import app
from app.models.processing_job import FlightInvestigation, FlightObservation, FlightReviewDecision, FlightReviewedExport
from app.reconciliation import ai, review, reviewed_exports as exports
from app.reconciliation.review import ReviewRequest
from app.services.job_processing import process_job
from test_flight_investigations import configured, install_provider, abstention
from test_flights_discrepancy_api import dataset
from test_flights_intake import csv_bytes, observation, submit


@pytest.fixture(autouse=True)
def isolated_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "OUTPUT_DIR", tmp_path / "output")


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def selected(client):
    job_id, _ = dataset(client)
    url = f"/api/v1/flights/jobs/{job_id}/discrepancies"
    summary = client.get(url).json()["discrepancies"][0]
    base = url + '/' + summary['discrepancy_id']
    evidence = client.get(base).json()
    return job_id, evidence, base


def body(evidence, action="override", revision=0, **fields):
    return dict(expected_evidence_digest=evidence['evidence_digest'], expected_revision=revision,
                request_id=uuid4().hex, action=action, reviewer_label="Local analyst", rationale="Reviewed supplied evidence.", **fields)


def decide(client, base, evidence, action="override", revision=0, **fields):
    response = client.post(base + '/review', json=body(evidence, action, revision, **fields))
    assert response.status_code == 200, response.text
    return response.json()


def ai_proposal(client, base, evidence):
    response = client.post(base + '/investigations', json={"expected_evidence_digest": evidence['evidence_digest'], "request_id": uuid4().hex})
    assert response.status_code == 200, response.text
    return response.json()


def freeze(client, job_id):
    base = f'/api/v1/flights/jobs/{job_id}/exports'
    snapshot = client.get(base + '/snapshot')
    assert snapshot.status_code == 200, snapshot.text
    payload = dict(expected_snapshot_digest=snapshot.json()['snapshot_digest'], request_id=uuid4().hex)
    response = client.post(base, json=payload)
    assert response.status_code == 200, response.text
    return response.json(), payload


def downloaded(client, job, result, key):
    response = client.get(f'/api/v1/flights/jobs/{job}/exports/{result["id"]}/download/{key}')
    assert response.status_code == 200, response.text
    content = response.content
    assert hashlib.sha256(content).hexdigest() == result['artifacts'][key]['sha256']
    return content


def csv_rows(content):
    return list(csv.DictReader(io.StringIO(content.decode('utf-8'), newline='')))


def test_accept_reject_override_and_history_preserve_raw_sources(client, configured, monkeypatch):
    calls = install_provider(monkeypatch)
    job, evidence, base = selected(client)
    assert client.get(base + '/review').json()['state'] == 'unreviewed'
    proposal = ai_proposal(client, base, evidence)
    candidate = proposal['recommendation']['candidate_id']
    with Session(engine) as session:
        before = [row.model_dump() for row in session.exec(select(FlightObservation)).all()]
    accepted = decide(client, base, evidence, 'accept', investigation_id=proposal['id'])
    assert accepted['candidate_id'] == candidate and accepted['revision'] == 1
    assert accepted['resolution']['origin'] == 'observed_candidate'
    rejected = decide(client, base, evidence, 'reject', 1, investigation_id=proposal['id'])
    assert rejected['candidate_id'] == candidate and rejected['resolution'] is None
    assert client.get(base + '/review').json()['state'] == 'rejected'
    alternative = next(c for c in evidence['candidates'] if c['candidate_id'] != candidate)
    overridden = decide(client, base, evidence, revision=2, candidate_id=alternative['candidate_id'], investigation_id=proposal['id'])
    assert overridden['resolution']['supporting_observation_ids'] == alternative['supporting_observation_ids']
    unresolved = decide(client, base, evidence, 'unresolved', 3)
    assert unresolved['resolution'] is None and unresolved['candidate_id'] is None
    current = client.get(base + '/review').json()
    assert current['state'] == 'unresolved' and current['revision'] == 4 and not current['reviewer_identity_verified']
    history = client.get(base + '/review/history?page_size=2').json()
    assert history['total'] == 4 and [e['revision'] for e in history['events']] == [1, 2]
    assert [e['revision'] for e in client.get(base + '/review/history?page_size=2&page=2').json()['events']] == [3, 4]
    with Session(engine) as session:
        assert [row.model_dump() for row in session.exec(select(FlightObservation)).all()] == before
    assert len(calls) == 1


def test_manual_assertions_without_ai_and_original_entered_text(client, monkeypatch):
    calls = install_provider(monkeypatch)
    _, evidence, base = selected(client)
    entered = '  09:47:12 a.m.  '
    result = decide(client, base, evidence, manual_value=entered)
    assert result['manual_value'] == entered
    assert result['candidate_id'] is None and result['investigation_id'] is None
    assert result['resolution'] == dict(origin='human_assertion', canonical_clock='09:47:12', precision='second', qualifiers=[],
                                         supporting_observation_ids=[], supporting_source_ids=[])
    assert client.get(base + '/review').json()['state'] == 'overridden'
    assert not calls


@pytest.mark.parametrize('manual', ['9:22', '', 'Contact Airline', '25:00', '9:22 AM (Estimated)', '<b>09:22 AM</b>'])
def test_ambiguous_unsupported_manual_replacements_are_refused(client, manual):
    _, evidence, base = selected(client)
    response = client.post(base + '/review', json=body(evidence, manual_value=manual))
    assert response.status_code == 422
    assert client.get(base + '/review').json()['revision'] == 0


def test_abstention_and_unavailability_do_not_prevent_manual_review(client, configured, monkeypatch):
    install_provider(monkeypatch, abstention())
    _, evidence, base = selected(client)
    abstained = ai_proposal(client, base, evidence)
    assert abstained['status'] == 'abstained'
    assert client.post(base + '/review', json=body(evidence, 'accept', investigation_id=abstained['id'])).status_code == 409
    assert decide(client, base, evidence, candidate_id=evidence['candidates'][0]['candidate_id'])['revision'] == 1
    monkeypatch.setattr(ai, 'OPENAI_API_KEY', '')
    assert decide(client, base, evidence, revision=1, manual_value='2:05 PM')['resolution']['canonical_clock'] == '14:05'


def test_idempotency_stale_revision_digest_and_invalid_payloads(client):
    _, evidence, base = selected(client)
    payload = body(evidence, candidate_id=evidence['candidates'][0]['candidate_id'])
    first = client.post(base + '/review', json=payload).json()
    assert client.post(base + '/review', json=payload).json() == first
    assert client.post(base + '/review', json={**payload, 'rationale': 'Different'}).status_code == 409
    assert client.post(base + '/review', json=body(evidence, 'unresolved')).status_code == 409
    stale = body(evidence, 'unresolved', 1)
    stale['expected_evidence_digest'] = 'sha256:' + '0' * 64
    assert client.post(base + '/review', json=stale).status_code == 409
    for changes in ({'candidate_id': 'foreign'}, {'candidate_id': None}, {'manual_value': '14:05'},
                    {'rationale': ''}, {'reviewer_label': ' '}, {'extra': 'forbidden'}, {'expected_revision': True}):
        invalid = {**body(evidence, revision=1, candidate_id=evidence['candidates'][0]['candidate_id']), **changes}
        assert client.post(base + '/review', json=invalid).status_code == 422
    assert client.post(base + '/review', json=body(evidence, 'unresolved', 1, candidate_id='hidden')).status_code == 422
    assert client.post(base + '/review', json=body(evidence, 'reject', 1)).status_code == 422
    assert client.get(base + '/review/history?page_size=101').status_code == 422


def test_cross_scope_candidates_investigations_and_stale_ai_are_rejected(client, configured, monkeypatch):
    install_provider(monkeypatch)
    _, evidence, base = selected(client)
    proposal = ai_proposal(client, base, evidence)
    _, other, other_base = selected(client)
    assert client.post(other_base + '/review', json=body(other, candidate_id=evidence['candidates'][0]['candidate_id'])).status_code == 422
    assert client.post(other_base + '/review', json=body(other, 'accept', investigation_id=proposal['id'])).status_code == 409
    monkeypatch.setattr(ai, 'OPENAI_MODEL', 'new-policy-model')
    assert client.post(base + '/review', json=body(evidence, 'accept', investigation_id=proposal['id'])).status_code == 409


def test_concurrent_different_decisions_do_not_lose_updates_and_exact_requests_replay(client, monkeypatch):
    job, evidence, _ = selected(client)
    original = review.read_evidence
    for same_key in (False, True):
        barrier = Barrier(2)
        def synchronized(*args):
            value = original(*args)
            barrier.wait(timeout=5)
            return value
        monkeypatch.setattr(review, 'read_evidence', synchronized)
        revision = 0 if not same_key else 1
        left = ReviewRequest(**body(evidence, 'unresolved', revision))
        right = left if same_key else ReviewRequest(**body(evidence, manual_value='14:05', revision=revision))
        def submit_one(payload):
            try: return review.submit_review(job, evidence['discrepancy_id'], payload)
            except HTTPException as error: return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit_one, (left, right)))
        if same_key:
            assert results[0]['id'] == results[1]['id']
        else:
            assert sum(isinstance(result, dict) for result in results) == 1 and 409 in results
    monkeypatch.setattr(review, 'read_evidence', original)
    with Session(engine) as session:
        assert sorted(e.revision for e in session.exec(select(FlightReviewDecision)).all()) == [1, 2]


def test_review_commit_failure_rolls_back(client, monkeypatch):
    _, evidence, base = selected(client)
    def fail(*args, **kwargs): raise OperationalError('private diagnostic', {}, Exception('secret'))
    with monkeypatch.context() as patch:
        patch.setattr(Session, 'commit', fail)
        response = client.post(base + '/review', json=body(evidence, manual_value='14:05'))
    assert response.status_code == 503 and 'secret' not in response.text
    assert client.get(base + '/review').json()['revision'] == 0


def test_exports_approved_values_exceptions_and_exact_cell_provenance(client, configured, monkeypatch):
    calls = install_provider(monkeypatch)
    job, evidence, base = selected(client)
    proposal = ai_proposal(client, base, evidence)
    accepted = decide(client, base, evidence, 'accept', investigation_id=proposal['id'])
    all_fields = client.get(base.rsplit('/', 1)[0] + '?kind=all').json()['discrepancies']
    field_base = base.rsplit('/', 1)[0]
    by_field = {entry['field']: entry for entry in all_fields if entry['flight'] == evidence['flight']}
    manual_summary = by_field['act_dep_time']
    manual = decide(client, field_base + '/' + manual_summary['discrepancy_id'], manual_summary, manual_value='2:06 PM')
    unresolved_summary = by_field['sched_arr_time']
    decide(client, field_base + '/' + unresolved_summary['discrepancy_id'], unresolved_summary, 'unresolved')
    exported, payload = freeze(client, job)
    reviewed = csv_rows(downloaded(client, job, exported, 'reviewed'))
    row = next(r for r in reviewed if r['flight'] == evidence['flight'])
    assert row['sched_dep_time'] == accepted['resolution']['canonical_clock'] and row['sched_dep_time_status'] == 'accepted'
    assert row['act_dep_time'] == '14:06' and row['act_dep_time_status'] == 'overridden'
    assert row['sched_arr_time'] == '' and row['sched_arr_time_status'] == 'unresolved'
    assert row['act_arr_time'] == '' and row['act_arr_time_status'] == 'unreviewed'
    exceptions = csv_rows(downloaded(client, job, exported, 'exceptions'))
    assert any(e['review_status'] == 'ungroupable' and e['tuple_id'] == 'ungroupable' for e in exceptions)
    manifest = json.loads(downloaded(client, job, exported, 'provenance'))
    assert manifest['snapshot_digest'] == payload['expected_snapshot_digest']
    entries = {e['discrepancy_id']: e for e in manifest['snapshot']['fields']}
    accepted_entry = entries[evidence['discrepancy_id']]
    assert {(o['tuple_id'], o['src']) for o in accepted_entry['observations']} == {('one', 'source-a'), ('two', 'source-b')}
    assert accepted_entry['decision']['id'] == accepted['id']
    assert entries[manual_summary['discrepancy_id']]['resolution']['supporting_observation_ids'] == []
    assert manifest['snapshot']['ungroupable_observations'][0]['fields'] == list(exports.TIME_FIELDS)
    assert len(calls) == 1


def test_rejected_export_stays_empty_and_old_export_is_frozen_after_rereview(client, configured, monkeypatch):
    install_provider(monkeypatch)
    job, evidence, base = selected(client)
    proposal = ai_proposal(client, base, evidence)
    decide(client, base, evidence, 'reject', investigation_id=proposal['id'])
    first, payload = freeze(client, job)
    before = {key: downloaded(client, job, first, key) for key in exports.ARTIFACTS}
    reviewed = csv_rows(before['reviewed'])[0]
    assert reviewed['sched_dep_time'] == '' and reviewed['sched_dep_time_status'] == 'rejected'
    decide(client, base, evidence, revision=1, manual_value='14:07')
    assert {key: downloaded(client, job, first, key) for key in exports.ARTIFACTS} == before
    replay = client.post(f'/api/v1/flights/jobs/{job}/exports', json=payload)
    assert replay.json()['id'] == first['id']
    second, _ = freeze(client, job)
    assert second['id'] != first['id'] and second['snapshot_digest'] != first['snapshot_digest']
    assert client.get(f'/api/v1/flights/jobs/{job}/exports?page_size=1').json()['total'] == 2
    assert client.get(f'/api/v1/flights/jobs/{job}/exports/{first["id"]}').json() == first


def test_stale_review_is_unapproved_and_new_revision_can_replace_it(client):
    job, evidence, base = selected(client)
    decide(client, base, evidence, manual_value='14:05')
    with Session(engine) as session:
        claim = session.get(FlightObservation, (job, 'one'))
        claim.sched_dep_time = '9:24 AM'  # Deliberate test corruption only.
        session.add(claim); session.commit()
    current = client.get(base + '/review').json()
    assert current['stale'] and current['state'] == 'unreviewed' and current['resolution'] is None
    exported, _ = freeze(client, job)
    row = csv_rows(downloaded(client, job, exported, 'reviewed'))[0]
    assert row['sched_dep_time'] == '' and row['sched_dep_time_status'] == 'stale'
    refreshed = client.get(base).json()
    assert decide(client, base, refreshed, revision=1, manual_value='14:06')['revision'] == 2


def test_export_render_is_deterministic_and_formula_escaping_is_reversible(client):
    content = csv_bytes([observation('=OBS(1)', src='@source', flight='=FORMULA'),
                         observation("'literal", src=' source', flight='')])
    job = submit(client, content)
    assert process_job(job) == 'completed'
    snapshot, checksum = exports.capture_snapshot(job)
    first = exports.render_snapshot(snapshot, checksum, 'a' * 32, '2026-01-01')
    assert first == exports.render_snapshot(snapshot, checksum, 'a' * 32, '2026-01-01')
    exception = csv_rows(first['exceptions'])[0]
    assert exception['flight'].startswith("'=") and exception['tuple_id'].startswith("'=")
    manifest = json.loads(first['provenance'])
    assert manifest['snapshot']['ungroupable_observations'][0]['tuple_id'] == '=OBS(1)'
    for raw in ('=1+1', '+1', '-1', '@SUM(1)', "'original", '  =1', '\t=1', 'a,"b"\nc', 'normal'):
        escaped = exports.spreadsheet_cell(raw)
        assert (escaped[1:] if escaped.startswith("'") else escaped) == raw
        parsed = list(csv.reader(io.StringIO(exports.csv_content(['x'], [{'x': raw}]).decode(), newline='')))
        assert parsed[1] == [escaped]


def test_stale_generation_and_file_failure_do_not_publish_metadata(client, monkeypatch):
    job, evidence, base = selected(client)
    export_base = f'/api/v1/flights/jobs/{job}/exports'
    snapshot = client.get(export_base + '/snapshot').json()
    payload = dict(expected_snapshot_digest=snapshot['snapshot_digest'], request_id=uuid4().hex)
    original = exports.write_artifacts
    def concurrent_review(identifier, data):
        final = original(identifier, data)
        review.submit_review(job, evidence['discrepancy_id'], ReviewRequest(**body(evidence, manual_value='14:05')))
        return final
    with monkeypatch.context() as patch:
        patch.setattr(exports, 'write_artifacts', concurrent_review)
        assert client.post(export_base, json=payload).status_code == 409
    assert client.get(export_base).json()['total'] == 0
    assert not list(exports.export_root().glob('[0-9a-f]' * 32))
    assert client.post(export_base, json=payload).status_code == 409
    refreshed = client.get(export_base + '/snapshot').json()
    def failed(*args, **kwargs): raise OSError('private filesystem error')
    with monkeypatch.context() as patch:
        patch.setattr(exports.os, 'fsync', failed)
        response = client.post(export_base, json=dict(expected_snapshot_digest=refreshed['snapshot_digest'], request_id=uuid4().hex))
    assert response.status_code == 503 and 'private' not in response.text
    assert client.get(export_base).json()['total'] == 0
    assert not list(exports.export_root().glob('.pending-*'))


def test_output_limit_missing_tampered_artifact_and_path_substitution(client, monkeypatch, tmp_path):
    job, _, _ = selected(client)
    with monkeypatch.context() as patch:
        patch.setattr(exports, 'MAX_EXPORT_BYTES', 10)
        snapshot, checksum = exports.capture_snapshot(job)
        with pytest.raises(HTTPException) as oversized:
            exports.render_snapshot(snapshot, checksum, 'b' * 32, 'now')
        assert oversized.value.status_code == 413
    result, _ = freeze(client, job)
    base = f'/api/v1/flights/jobs/{job}/exports/{result["id"]}'
    assert client.get(base + '/download/../../input').status_code in (404, 422)
    assert client.get(base + '/download/other.csv').status_code == 422
    path = exports.export_root() / result['id'] / 'reviewed.csv'
    data = path.read_bytes()
    path.write_bytes(b'tampered')
    assert client.get(base + '/download/reviewed').status_code == 409
    path.unlink()
    assert client.get(base + '/download/reviewed').status_code == 404
    outside = tmp_path / 'private.csv'; outside.write_bytes(data)
    path.symlink_to(outside)
    assert client.get(base + '/download/reviewed').status_code == 404
    path.unlink(); path.write_bytes(data)
    assert client.get(base.replace(f'/jobs/{job}/', '/jobs/99999/') + '/download/reviewed').status_code == 404


def test_review_and_export_only_insert_new_feature_rows(client):
    from app.core.config import INPUT_DIR
    from app.models.processing_job import ProcessingJob, JobImport
    job, evidence, base = selected(client)
    with Session(engine) as session:
        before = [row.model_dump() for row in session.exec(select(FlightObservation)).all()]
        job_before = session.get(ProcessingJob, job).model_dump()
        metadata_before = session.get(JobImport, job).model_dump()
    path = INPUT_DIR / job_before['filename_input_saved']
    original = path.read_bytes()
    statements = []
    def sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().upper())
    event.listen(engine, 'before_cursor_execute', sql)
    try:
        decide(client, base, evidence, manual_value='2:09 PM')
        result, _ = freeze(client, job)
        for artifact in exports.ARTIFACTS: downloaded(client, job, result, artifact)
    finally:
        event.remove(engine, 'before_cursor_execute', sql)
    assert not any(s.startswith(('UPDATE', 'DELETE')) for s in statements)
    assert all(s.startswith(('INSERT INTO FLIGHT_REVIEW_DECISIONS', 'INSERT INTO FLIGHT_REVIEWED_EXPORTS'))
               for s in statements if s.startswith('INSERT'))
    with Session(engine) as session:
        assert [row.model_dump() for row in session.exec(select(FlightObservation)).all()] == before
        assert session.get(ProcessingJob, job).model_dump() == job_before
        assert session.get(JobImport, job).model_dump() == metadata_before
    assert path.read_bytes() == original


def test_export_database_failure_retains_only_unpublished_unique_files(client, monkeypatch):
    job, _, _ = selected(client)
    base = f'/api/v1/flights/jobs/{job}/exports'
    snapshot = client.get(base + '/snapshot').json()
    payload = dict(expected_snapshot_digest=snapshot['snapshot_digest'], request_id=uuid4().hex)
    def failed(*args, **kwargs): raise OperationalError('private commit diagnostic', {}, Exception('secret'))
    with monkeypatch.context() as patch:
        patch.setattr(Session, 'commit', failed)
        response = client.post(base, json=payload)
    assert response.status_code == 503 and 'secret' not in response.text
    assert client.get(base).json()['total'] == 0
    orphans = list(exports.export_root().iterdir())
    assert len(orphans) == 1
    assert client.get(base + '/' + orphans[0].name + '/download/reviewed').status_code == 404
    # An ambiguous acknowledgement could also follow a successful commit. Keeping
    # complete unique files is safe; no metadata means they are never downloadable.
    retry = client.post(base, json=payload)
    assert retry.status_code == 200 and retry.json()['id'] != orphans[0].name


def test_export_conflicting_request_reuse_and_snapshot_errors(client):
    from app.models.processing_job import JobImport, ProcessingJob
    job, evidence, base = selected(client)
    exported, payload = freeze(client, job)
    export_base = f'/api/v1/flights/jobs/{job}/exports'
    assert client.post(export_base, json={**payload, 'expected_snapshot_digest': 'sha256:' + '0' * 64}).status_code == 409
    assert client.get(export_base + '?page=0').status_code == 422
    assert client.get(export_base + '/' + '0' * 32).status_code == 404
    assert client.get('/api/v1/flights/jobs/99999/exports/snapshot').status_code == 404
    assert client.get(base.replace(evidence['discrepancy_id'], 'unknown') + '/review').status_code == 404
    pending = submit(client)
    assert client.get(f'/api/v1/flights/jobs/{pending}/exports/snapshot').status_code == 409
    with Session(engine) as session:
        metadata = session.get(JobImport, job)
        metadata.options = {'contract_version': 999}
        session.add(metadata); session.commit()
    assert client.get(export_base + '/snapshot').status_code == 409
    # Frozen downloads remain available independently of later source corruption.
    assert downloaded(client, job, exported, 'reviewed')


def test_corrupt_reviewed_value_never_publishes_an_export(client):
    job, evidence, base = selected(client)
    decided = decide(client, base, evidence, candidate_id=evidence['candidates'][0]['candidate_id'])
    with Session(engine) as session:
        row = session.get(FlightReviewDecision, decided['id'])
        row.resolution = {**row.resolution, 'canonical_clock': 'invented'}
        session.add(row); session.commit()
    assert client.get(base + '/review').status_code == 409
    assert client.get(f'/api/v1/flights/jobs/{job}/exports/snapshot').status_code == 409


def test_export_namespace_rejects_symlink_substitution(client, tmp_path):
    job, _, _ = selected(client)
    exports.OUTPUT_DIR.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (exports.OUTPUT_DIR / 'flight-reviewed').symlink_to(outside, target_is_directory=True)
    base = f'/api/v1/flights/jobs/{job}/exports'
    snapshot = client.get(base + '/snapshot').json()
    response = client.post(base, json=dict(expected_snapshot_digest=snapshot['snapshot_digest'], request_id=uuid4().hex))
    assert response.status_code == 409 and list(outside.iterdir()) == []


def test_0006_upgrade_preserves_legacy_flights_ai_and_enforces_new_constraints(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    isolated = create_engine(f'sqlite:///{tmp_path}/review-migration.db')
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    with isolated.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        connection.commit()
        config.attributes['connection'] = connection
        command.upgrade(config, '0005')
        connection.execute(text('''INSERT INTO processing_jobs
            (id, filename_original, filename_input_saved, filename_cleaned, filename_error_report,
             status, total_rows, valid_rows, invalid_rows, created_at, processed_at, job_kind)
            VALUES (42, 'legacy.csv', 'input.csv', 'output.csv', '', 'completed', 1, 1, 0,
                    '2026-01-01', '2026-01-01', 'transactions')'''))
        connection.execute(text('''INSERT INTO flight_observations
            (job_id, tuple_id, row_number, src, flight, sched_dep_time, act_dep_time, sched_arr_time, act_arr_time, issues)
            VALUES (42, 'opaque', 2, 'synthetic-source', 'ZZ-1', '9:22 AM', '', '', '', '[]')'''))
        connection.execute(text('''INSERT INTO flight_investigations
            (id, request_id, job_id, discrepancy_id, evidence_digest, config_fingerprint,
             status, provider_attempted, attempt_number, policy_version, prompt_version, schema_version, usage, created_at)
            VALUES ('ai-history', 'ai-request', 42, 'scope', 'digest', 'config', 'abstained', 0, 0, 'policy', 'prompt', 'schema', '{}', '2026-01-01')'''))
        connection.commit()
        before = {name: connection.execute(text('SELECT * FROM ' + name)).all()
                  for name in ('processing_jobs', 'flight_observations', 'flight_investigations')}
        command.upgrade(config, 'head'); connection.commit()
        for name, values in before.items():
            assert connection.execute(text('SELECT * FROM ' + name)).all() == values
        assert {'flight_review_decisions', 'flight_reviewed_exports'} <= set(inspect(connection).get_table_names())
        insert = text('''INSERT INTO flight_review_decisions
            (id, request_id, request_fingerprint, job_id, discrepancy_id, flight, field, evidence_digest,
             revision, action, investigation_id, rationale, reviewer_label, policy_version, normalization_policy, detection_policy, created_at)
            VALUES (:id, :request, 'fingerprint', :job, 'scope', 'ZZ-1', 'sched_dep_time', 'digest',
                    :revision, :action, :investigation, '', 'local', 'review', 'normalization', 'detection', '2026-01-01')''')
        valid = dict(id='event-1', request='request-1', job=42, revision=1, action='unresolved', investigation=None)
        connection.execute(insert, valid); connection.commit()
        for changes in (dict(id='event-2', request='request-2'), dict(id='event-2', revision=2),
                        dict(id='orphan', request='new', job=999), dict(id='invalid', request='new', revision=0),
                        dict(id='invalid', request='new', revision=2, action='approve'),
                        dict(id='invalid', request='new', revision=2, investigation='unknown')):
            with pytest.raises(IntegrityError): connection.execute(insert, {**valid, **changes})
            connection.rollback()
        assert connection.execute(text('SELECT count(*) FROM flight_review_decisions')).scalar() == 1
    isolated.dispose()


def test_review_waits_until_frozen_export_metadata_commits(client, monkeypatch):
    from threading import Event
    job, evidence, _ = selected(client)
    snapshot, checksum = exports.capture_snapshot(job)
    projected, finished = Event(), Event()
    original_capture, original_read = exports.capture_snapshot, review.read_evidence
    worker_results, workers = [], []
    def observed_read(*args):
        value = original_read(*args)
        projected.set()
        return value
    def review_one():
        try:
            worker_results.append(review.submit_review(job, evidence['discrepancy_id'], ReviewRequest(**body(evidence, manual_value='14:05'))))
        except Exception as error:
            worker_results.append(error)
        finally:
            finished.set()
    def capture_with_contender(*args, **kwargs):
        if kwargs.get('session') is not None:
            from threading import Thread
            worker = Thread(target=review_one)
            workers.append(worker); worker.start()
            assert projected.wait(timeout=3)
            assert not finished.wait(timeout=0.05)  # Review is blocked by publication gate.
        return original_capture(*args, **kwargs)
    monkeypatch.setattr(review, 'read_evidence', observed_read)
    monkeypatch.setattr(exports, 'capture_snapshot', capture_with_contender)
    result = exports.create_export(job, checksum, uuid4().hex)
    for worker in workers: worker.join(timeout=5)
    assert finished.is_set() and isinstance(worker_results[0], dict), worker_results
    frozen = json.loads(exports.artifact_bytes(job, result['id'], 'provenance'))
    entry = next(e for e in frozen['snapshot']['fields'] if e['discrepancy_id'] == evidence['discrepancy_id'])
    assert entry['decision'] is None and entry['resolution'] is None and entry['status'] == 'unreviewed'
    assert review.get_review(job, evidence['discrepancy_id'])['revision'] == 1


def test_concurrent_export_retries_publish_one_snapshot(client, monkeypatch):
    job, _, _ = selected(client)
    _, checksum = exports.capture_snapshot(job)
    key, barrier = uuid4().hex, Barrier(2)
    original = exports.write_artifacts
    def overlap(*args):
        result = original(*args)
        barrier.wait(timeout=5)
        return result
    monkeypatch.setattr(exports, 'write_artifacts', overlap)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: exports.create_export(job, checksum, key), range(2)))
    assert results[0] == results[1]
    assert len(list(exports.export_root().iterdir())) == 1
    with Session(engine) as session:
        assert len(session.exec(select(FlightReviewedExport)).all()) == 1
