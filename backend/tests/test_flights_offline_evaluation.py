"""Interop of actual disposable backend exports with file-only offline evaluation."""

import json
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, select

from app.core.db import engine
from app.main import app
from app.models.processing_job import FlightObservation, FlightReviewDecision, FlightReviewedExport
from app.reconciliation import reviewed_exports
from app.services.job_processing import process_job
from test_flights_intake import csv_bytes, observation, submit


def load_evaluator():
    scripts = Path(__file__).resolve().parents[2] / 'scripts'
    sys.path.insert(0, str(scripts))
    import evaluate_flights
    return evaluate_flights


def test_real_backend_export_contract_is_valid_offline_without_operational_writes(tmp_path, monkeypatch):
    evaluator = load_evaluator()
    monkeypatch.setattr(reviewed_exports, 'OUTPUT_DIR', tmp_path / 'runtime-output')
    root = tmp_path / 'benchmark'
    for directory in ('observed','reference','export'): (root / directory).mkdir(parents=True)
    rows = [observation('one', src=' source ', value='13:00'), observation('two', src='source-b', value='14:00'),
            observation('=opaque', src='', flight='', value='')]
    dirty = csv_bytes(rows)
    reference_rows = [list(row) for row in reversed(rows)]
    for row in reference_rows:
        if row[2]: row[3] = '13:00'
    reference = csv_bytes(reference_rows)
    (root/'observed/dirty.csv').write_bytes(dirty)
    (root/'reference/clean.csv').write_bytes(reference)
    with TestClient(app) as client:
        job = submit(client, dirty)
        assert process_job(job) == 'completed'
        base = f'/api/v1/flights/jobs/{job}'
        selected = client.get(base+'/discrepancies?field=sched_dep_time').json()['discrepancies'][0]
        evidence = client.get(base+'/discrepancies/'+selected['discrepancy_id']).json()
        decision = client.post(base+'/discrepancies/'+selected['discrepancy_id']+'/review', json=dict(
            expected_evidence_digest=evidence['evidence_digest'], expected_revision=0, request_id=uuid4().hex,
            action='override', reviewer_label='Synthetic reviewer', rationale='Synthetic evidence reviewed.',
            candidate_id=evidence['candidates'][0]['candidate_id']))
        assert decision.status_code == 200, decision.text
        snapshot = client.get(base+'/exports/snapshot').json()
        exported = client.post(base+'/exports', json=dict(expected_snapshot_digest=snapshot['snapshot_digest'], request_id=uuid4().hex)).json()
        (root/'metadata.json').write_text(json.dumps(exported))
        for key, filename in evaluator.FILES.items():
            content = client.get(base+'/exports/'+exported['id']+'/download/'+key)
            assert content.status_code == 200
            (root/'export'/filename).write_bytes(content.content)
    source=dict(synthetic=True,dataset_type='raha_flights_v1',files={'observed':{'sha256':evaluator.sha(dirty)},'evaluation_reference':{'sha256':evaluator.sha(reference)}})
    (root/'synthetic.json').write_text(json.dumps(source))
    with Session(engine) as session:
        before = {model.__tablename__: [row.model_dump() for row in session.exec(select(model)).all()]
                  for model in (FlightObservation, FlightReviewDecision, FlightReviewedExport)}
    statements=[]
    def sql(connection,cursor,statement,parameters,context,executemany): statements.append(statement)
    event.listen(engine,'before_cursor_execute',sql)
    try:
        report=evaluator.evaluate(root/'export',root/'metadata.json',root/'observed/dirty.csv',root/'reference/clean.csv',synthetic_manifest=root/'synthetic.json')
    finally:
        event.remove(engine,'before_cursor_execute',sql)
    assert statements == []
    assert report['exact_string']['counts']['corrected_errors'] == 1
    assert report['alignment']['ungroupable_observations'] == 1
    with Session(engine) as session:
        for model in (FlightObservation, FlightReviewDecision, FlightReviewedExport):
            assert [row.model_dump() for row in session.exec(select(model)).all()] == before[model.__tablename__]


def test_runtime_has_no_evaluator_imports_or_evaluation_api():
    import ast
    root = Path(__file__).resolve().parents[1]/'app'
    for path in root.rglob('*.py'):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert 'evaluate_flights' not in (node.module or '')
            elif isinstance(node,ast.Import):
                assert all('evaluate_flights' not in alias.name for alias in node.names)
    assert not any('evaluat' in route.path for route in app.routes)
