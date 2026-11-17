"""Read-only Flights history and schema interoperability on disposable state."""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session
from app.core.db import engine
from app.main import app
from app.models.processing_job import ProcessingJob
from app.reconciliation.evidence import FieldEvidence, investigate_field
from app.reconciliation.grouping import RawObservation, group_flights
from app.services.job_processing import process_job
from test_flights_intake import submit
from test_uploads import VALID_CSV

@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value

def test_history_flights_only_order_pagination_status_and_readonly(client):
    old = client.post('/api/v1/uploads', files={'file': ('legacy.csv', VALID_CSV, 'text/csv')})
    assert old.status_code == 202
    ids = [submit(client) for _ in range(3)]
    assert process_job(ids[0]) == 'completed'
    with Session(engine) as session:
        for identifier in ids:
            job = session.get(ProcessingJob, identifier)
            job.created_at = datetime(2026, 1, 1)
            session.add(job)
        session.commit()
    statements = []
    def sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', sql)
    try:
        first = client.get('/api/v1/flights/jobs?page_size=2').json()
        second = client.get('/api/v1/flights/jobs?page_size=2&page=2').json()
        completed = client.get('/api/v1/flights/jobs?status=completed').json()
    finally:
        event.remove(engine, 'before_cursor_execute', sql)
    assert first['total'] == 3 and [j['id'] for j in first['jobs']] == ids[:0:-1]
    assert [j['id'] for j in second['jobs']] == ids[:1]
    assert [j['id'] for j in completed['jobs']] == ids[:1]
    row = completed['jobs'][0]
    assert row['job_kind'] == 'raha_flights_v1' and row['contract_version'] == 1
    assert row['observation_count'] == 1 and row['file_size'] > 0 and row['processed_at']
    assert 'filename_input_saved' not in row and 'input_sha256' not in row
    assert all(not s.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'ALTER')) for s in statements)
    assert len(statements) <= 6  # Count + bounded outer-join per request, no related-row N+1.

@pytest.mark.parametrize('query', ['page=0', 'page_size=101', 'status=approved'])
def test_history_bounds(client, query):
    assert client.get('/api/v1/flights/jobs?' + query).status_code == 422

def test_empty_history_and_storage_failure(client, monkeypatch):
    assert client.get('/api/v1/flights/jobs').json()['jobs'] == []
    def failed(*args, **kwargs):
        raise OperationalError('private query', {}, RuntimeError('private details'))
    monkeypatch.setattr(Session, 'exec', failed)
    response = client.get('/api/v1/flights/jobs')
    assert response.status_code == 503 and response.json()['detail'] == 'Flights history storage is unavailable.'

def test_frontend_evidence_fixture_matches_backend_schema_and_computation():
    path = Path(__file__).resolve().parents[2] / 'frontend/scripts/fixtures/investigation.json'
    fixture = json.loads(path.read_text())
    typed = TypeAdapter(FieldEvidence).validate_python(fixture)
    rows = [RawObservation(typed.job_id, c.tuple_id, c.row_number, c.src, typed.flight,
                           c.normalization.raw, '', '', '') for c in typed.claims]
    reconstructed = investigate_field(group_flights(rows).groups[0], typed.field)
    assert json.loads(json.dumps(asdict(reconstructed))) == fixture
