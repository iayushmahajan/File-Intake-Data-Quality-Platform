"""Evidence runner: existing empty test SQLite ONLY; no DB creation, DDL, network or AI.

Uses real application API handlers and persistence in-process, not mocked responses.
Refuses reuse after the run; it never resets or cleans a database.
"""
import argparse
import faulthandler
faulthandler.enable()
faulthandler.dump_traceback_later(45, exit=True)
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument('--database', required=True, type=Path)
parser.add_argument('--evidence-dir', required=True, type=Path)
args = parser.parse_args()
db = args.database.absolute()
root = db.parent
assert root.parent == Path('/tmp') and root.name.startswith('file-intake-tests-')
assert db.name == 'tests.db' and root.is_dir() and db.is_file()
assert db.resolve() == db and root.resolve() == root
assert root.stat().st_uid == os.getuid() and root.stat().st_mode & 0o777 == 0o700
assert db.stat().st_nlink == 1
inode = (db.stat().st_dev, db.stat().st_ino)
with sqlite3.connect(db.as_uri() + '?mode=ro&immutable=1', uri=True) as c:
    schema_before = c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    assert c.execute('SELECT version_num FROM alembic_version').fetchall() == [('0006',)]
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert all(c.execute('SELECT count(*) FROM "' + t + '"').fetchone()[0] == 0 for t in tables if t != 'alembic_version'), 'Refusing a nonempty test database'
    c.execute('PRAGMA query_only=ON')

storage = root / 'product-validation-m1'
assert not storage.exists() and not args.evidence_dir.exists(), 'Refusing existing artifacts'
os.umask(0o077)
# Every runtime resource is selected before any application import. rw refuses creation.
os.environ.update(DATABASE_URL=f'sqlite:///file:{db}?mode=rw&uri=true', DATA_DIR=str(storage),
                  CELERY_BROKER_URL='memory://', CELERY_QUEUE='product-validation-m1',
                  OPENAI_API_KEY='', OPENAI_BASE_URL='https://unconfigured.invalid', OPENAI_MODEL='disabled-validation')
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend'))
from sqlalchemy import event, text
from sqlmodel import Session, select
from fastapi.testclient import TestClient
from app.core import db as persistence, config
from app import main
from app.models.processing_job import FlightObservation
from app.services.job_processing import process_job
from app.reconciliation import ai, reviewed_exports

assert persistence.engine.url.query['mode'] == 'rw'
assert persistence.engine.dialect.create_connect_args(persistence.engine.url)[0] == [f'file:{db}?mode=rw']
assert config.DATA_DIR == storage and config.CELERY_BROKER_URL == 'memory://' and config.OPENAI_API_KEY == ''
assert not storage.is_relative_to(Path.cwd() / 'backend' / 'data')

sql_verbs = {}
@event.listens_for(persistence.engine, 'before_cursor_execute')
def forbid_schema_and_deletes(connection, cursor, statement, parameters, context, executemany):
    verb = statement.lstrip().split(None, 1)[0].upper()
    assert verb not in {'CREATE', 'DROP', 'ALTER', 'DELETE', 'REPLACE', 'ATTACH', 'DETACH', 'VACUUM'}, 'Forbidden SQL: ' + verb
    assert not (verb == 'UPDATE' and 'flight_observations' in statement.lower()), 'Raw evidence update forbidden'
    sql_verbs[verb] = sql_verbs.get(verb, 0) + 1

def forbidden(*a, **kw):
    raise AssertionError('Network/provider/migration invocation forbidden')
async def forbidden_provider(*a, **kw):
    forbidden()
main.migrate_database = forbidden
persistence.migrate_database = forbidden
ai.call_provider = forbidden_provider
socket.socket.connect = forbidden
# Deliberately do not enter TestClient's lifespan context: startup migrates databases.
client = TestClient(main.app)
print("Isolation guards installed; beginning in-process requests.", flush=True)
checks = []
def api(method, path, expected=200, **kwargs):
    assert not (method == 'POST' and '/investigations' in path)
    response = client.request(method, path, **kwargs)
    assert response.status_code == expected, (method, path, response.status_code, response.text)
    checks.append({'method': method, 'path': path, 'status': response.status_code})
    return response

def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8'), newline='')))
def sha(data):
    return hashlib.sha256(data).hexdigest()
def observations():
    with Session(persistence.engine) as session:
        records = session.exec(select(FlightObservation).order_by(FlightObservation.job_id, FlightObservation.tuple_id)).all()
        data = [r.model_dump(mode='json') for r in records]
    return sha(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()), data

# Deliberately synthetic, operator-authored scenario. No historical ground truth/reference.
header = ['tuple_id','src','flight','sched_dep_time','act_dep_time','sched_arr_time','act_arr_time']
fixture = [
 ['pv-a-1','source-a','ZZ-100-AAA-BBB','16:30','17:08','18:00','18:10'],
 ['pv-a-2','source-b','ZZ-100-AAA-BBB','16:30','17:09','18:00','18:10'],
 ['pv-a-3','source-b','ZZ-100-AAA-BBB','16:30','17:09','18:00','18:10'],
 ['pv-b-1','source-a','ZZ-200-CCC-DDD','10:00','10:05','11:00',''],
 ['pv-b-2','source-b','ZZ-200-CCC-DDD','10:00','10:05','11:00','Not Available'],
 ['pv-c-1','source-a','ZZ-300-EEE-FFF','9:00 AM','09:05','10:00','10:05'],
 ['pv-c-2','source-b','ZZ-300-EEE-FFF','09:00 a.m.','09:05','10:00','10:05'],
]
stream = io.StringIO(newline=''); writer = csv.writer(stream); writer.writerow(header); writer.writerows(fixture)
content = stream.getvalue().encode()
accepted = api('POST', '/api/v1/flights/uploads', 202, files={'file':('synthetic-validation.csv', content, 'text/csv')}).json()
job = accepted['job_id']; base = f'/api/v1/flights/jobs/{job}'
assert api('GET', base).json()['status'] == 'pending'
assert process_job(job) == 'completed'
assert process_job(job) == 'ignored'  # duplicate delivery cannot republish evidence
job_before = api('GET', base).json()
assert job_before['status'] == 'completed' and job_before['observation_count'] == 7
assert job_before['input_sha256'] == sha(content)
source_path = config.INPUT_DIR / job_before['filename_input_saved']
assert source_path.read_bytes() == content
fingerprint_before, original = observations()
page = api('GET', base + '/discrepancies?kind=all&page_size=100').json()
assert page['total'] == 12
case = {(s['flight'], s['field']): api('GET', base+'/discrepancies/'+s['discrepancy_id']).json() for s in page['discrepancies'] if (s['flight'], s['field']) in [('ZZ-100-AAA-BBB','act_dep_time'),('ZZ-200-CCC-DDD','act_arr_time'),('ZZ-300-EEE-FFF','sched_dep_time')]}
a,b,c = [case[key] for key in [('ZZ-100-AAA-BBB','act_dep_time'),('ZZ-200-CCC-DDD','act_arr_time'),('ZZ-300-EEE-FFF','sched_dep_time')]]
assert a['flags']['confirmed_conflict']
assert [(v['canonical_clock'],v['distinct_source_support_count'],v['observation_support_count']) for v in a['candidates']] == [('17:08',1,1),('17:09',1,2)]
assert a['baseline']['status'] == 'abstain'
assert b['flags']['has_missing'] and b['flags']['has_placeholders'] and not b['candidates']
assert len(c['candidates']) == 1 and c['candidates'][0]['canonical_clock'] == '09:00'
assert c['flags']['formatting_variation'] and not c['flags']['confirmed_conflict']

def review_path(e): return base+'/discrepancies/'+e['discrepancy_id']+'/review'
def decision(e, revision, action, rationale, **fields):
    return dict(expected_evidence_digest=e['evidence_digest'],expected_revision=revision,request_id=uuid4().hex,
                action=action,reviewer_label='Synthetic validation reviewer',rationale=rationale,**fields)
selected = c['candidates'][0]
payload = decision(c,0,'override','Synthetic fixture: both source spellings support 09:00; evidence-supported judgment, not independently verified historical truth.', candidate_id=selected['candidate_id'])
first = api('POST', review_path(c), json=payload).json()
assert first['revision'] == 1 and first['resolution']['canonical_clock'] == '09:00'
assert first['resolution']['supporting_observation_ids'] == selected['supporting_observation_ids']
assert api('POST', review_path(c), json=payload).json() == first
api('POST', review_path(c), 409, json={**payload,'rationale':'Conflicting reuse'})
api('POST', review_path(c), 409, json=decision(c,0,'unresolved','Stale revision exercise'))
api('POST', review_path(c), 409, json={**decision(c,1,'unresolved','Stale digest exercise'),'expected_evidence_digest':'sha256:'+'0'*64})
second = api('POST', review_path(c), json=decision(c,1,'override','Re-review confirms the same source-supported clock; the first event must remain in history.',candidate_id=selected['candidate_id'])).json()
assert second['revision'] == 2 and second['id'] != first['id']
unresolved = api('POST', review_path(b), json=decision(b,0,'unresolved','One report is empty and the other unavailable; there is no supported arrival clock to approve.')).json()
assert unresolved['resolution'] is None and unresolved['candidate_id'] is None

# New API client and disposed connection pool demonstrate independent database sessions.
client.close(); persistence.engine.dispose(); client = TestClient(main.app)
current_c = api('GET', review_path(c)).json(); current_b = api('GET', review_path(b)).json()
assert current_c['state'] == 'overridden' and current_c['revision'] == 2
assert current_c['decision']['reviewer_label'] == payload['reviewer_label']
assert current_b['state'] == 'unresolved' and current_b['resolution'] is None
history_c = api('GET',review_path(c)+'/history?page_size=1&page=1').json()
history_c2 = api('GET',review_path(c)+'/history?page_size=1&page=2').json()
assert history_c['total'] == 2 and history_c['events'][0]['id'] == first['id'] and history_c2['events'][0]['id'] == second['id']
assert history_c['events'][0]['rationale'] == payload['rationale']

snapshot = api('GET',base+'/exports/snapshot').json()
export_payload = dict(expected_snapshot_digest=snapshot['snapshot_digest'],request_id=uuid4().hex)
export = api('POST',base+'/exports',json=export_payload).json()
assert api('POST',base+'/exports',json=export_payload).json() == export
api('POST',base+'/exports',409,json={**export_payload,'expected_snapshot_digest':'sha256:'+'0'*64})
artifacts = {}
for key in ['reviewed','exceptions','provenance']:
    data = api('GET',base+f'/exports/{export["id"]}/download/{key}').content
    assert len(data) == export['artifacts'][key]['bytes'] and sha(data) == export['artifacts'][key]['sha256']
    artifacts[key] = data
reviewed = rows(artifacts['reviewed']); exceptions = rows(artifacts['exceptions']); provenance = json.loads(artifacts['provenance'])
by_flight = {r['flight']:r for r in reviewed}
assert by_flight[c['flight']]['sched_dep_time'] == '09:00'
assert by_flight[c['flight']]['sched_dep_time_status'] == 'overridden'
assert by_flight[c['flight']]['sched_dep_time_decision_id'] == second['id']
assert by_flight[b['flight']]['act_arr_time'] == '' and by_flight[b['flight']]['act_arr_time_status'] == 'unresolved'
assert by_flight[a['flight']]['act_dep_time'] == '' and by_flight[a['flight']]['act_dep_time_status'] == 'unreviewed'
assert all(r[field] == '' for r in reviewed for field in ['sched_dep_time','act_dep_time','sched_arr_time','act_arr_time'] if (r['flight'],field) != (c['flight'],'sched_dep_time'))
assert len(reviewed) == 3 and len(exceptions) == 11
assert any(r['flight']==b['flight'] and r['field']=='act_arr_time' and r['review_status']=='unresolved' for r in exceptions)
entries = {r['discrepancy_id']:r for r in provenance['snapshot']['fields']}
assert entries[c['discrepancy_id']]['decision']['id'] == second['id']
assert {r['tuple_id'] for r in entries[c['discrepancy_id']]['observations']} == {'pv-c-1','pv-c-2'}
assert provenance['snapshot']['input_sha256'] == sha(content)
rerendered = reviewed_exports.render_snapshot(provenance['snapshot'],export['snapshot_digest'],export['id'],provenance['generated_at'])
assert rerendered == artifacts

# Later review appends history but cannot change the existing frozen snapshot.
later = api('POST',review_path(b),json=decision(b,1,'unresolved','Revisited: no additional source evidence; retain unresolved with this new event.')).json()
assert later['revision'] == 2
assert api('GET',base+'/exports/snapshot').json()['snapshot_digest'] != snapshot['snapshot_digest']
api('POST',base+'/exports',409,json={**export_payload,'request_id':uuid4().hex})
assert api('POST',base+'/exports',json=export_payload).json() == export
for key in artifacts:
    assert api('GET',base+f'/exports/{export["id"]}/download/{key}').content == artifacts[key]
assert api('GET',base+f'/exports/{export["id"]}').json() == export
assert api('GET',base+'/exports').json()['total'] == 1
assert api('GET',review_path(b)+'/history').json()['total'] == 2
fingerprint_after, after = observations()
assert after == original and fingerprint_before == fingerprint_after and source_path.read_bytes() == content
assert api('GET',base).json() == job_before
client.close();persistence.engine.dispose()
with sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True) as connection:
    schema_after = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    assert schema_before == schema_after
    counts = {t:connection.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables}
assert counts['processing_jobs']==1 and counts['flight_observations']==7 and counts['flight_review_decisions']==4 and counts['flight_reviewed_exports']==1 and counts['flight_investigations']==0
assert (db.stat().st_dev,db.stat().st_ino)==inode
result = dict(passed=True, database=str(db), existing_database_reused=True, database_created=False, migration_executed=False,
              storage=str(storage), broker='memory://', queue=config.CELERY_QUEUE, transport='in-process TestClient; no lifespan/network',
              fixture_sha256=sha(content), observation_sha256_before=fingerprint_before,observation_sha256_after=fingerprint_after,
              job_id=job, cases={label:case for label,case in [('A',a),('B',b),('C',c)]},
              decisions=[first,second,unresolved,later], export_metadata=export, table_counts=counts, sql_verbs=sql_verbs,
              api_checks=checks, artifact_checks={key:{'sha256':sha(data),'bytes':len(data)} for key,data in artifacts.items()},
              reviewed_rows=len(reviewed), exception_rows=len(exceptions), approved_field_count=1,
              schema_unchanged=True, browser_persistence_verified=False, ai_calls=0)
faulthandler.cancel_dump_traceback_later()
args.evidence_dir.mkdir(parents=True,exist_ok=False)
(args.evidence_dir/'synthetic-observations.csv').write_bytes(content)
for key,name in reviewed_exports.ARTIFACTS.items(): (args.evidence_dir/name).write_bytes(artifacts[key])
(args.evidence_dir/'export-metadata.json').write_text(json.dumps(export,indent=2)+'\n')
(args.evidence_dir/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'api_checks':len(checks),'counts':counts,'approved_fields':1,'exception_rows':11,'observation_sha256':fingerprint_after,'sql_verbs':sql_verbs}))
