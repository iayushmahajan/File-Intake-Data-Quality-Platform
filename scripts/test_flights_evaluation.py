"""Offline evaluator tests use synthetic bytes and frozen v1 artifact contracts only."""

import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

import evaluate_flights as ev


def csv_bytes(header, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream); writer.writerow(header); writer.writerows(rows)
    return stream.getvalue().encode()


def observation(key, source, flight, value):
    return [key, source, flight, value, "16:00", "16:00", "16:00"]


def fixture(root, dirty_rows=None, reference_rows=None, decisions=None):
    dirty_rows = dirty_rows if dirty_rows is not None else [
        observation('a1','s1','ZZ-1-AAA-BBB','13:00'), observation('a2','s2','ZZ-1-AAA-BBB','14:00'),
        observation('b1','s1','ZZ-2-AAA-BBB','14:00'), observation('b2','s2','ZZ-2-AAA-BBB','14:00'),
        observation('c1','s1','ZZ-3-AAA-BBB','13:00'), observation('c2','s2','ZZ-3-AAA-BBB','13:00'),
        observation('d1','s1','ZZ-4-AAA-BBB','13:00'), observation('d2','s2','ZZ-4-AAA-BBB','13:00'),
        observation('e1','s1','ZZ-5-AAA-BBB','13:00')]
    if reference_rows is None:
        reference_rows = copy.deepcopy(dirty_rows)
        for row in reference_rows:
            row[3] = '13:00' if row[2] in ('ZZ-1-AAA-BBB','ZZ-5-AAA-BBB') else '14:00'
    for directory in ('observed','reference','export'): (root/directory).mkdir(parents=True)
    dirty, reference = root/'observed/dirty.csv', root/'reference/clean.csv'
    dirty.write_bytes(csv_bytes(ev.HEADER, dirty_rows)); reference.write_bytes(csv_bytes(ev.HEADER, reference_rows))
    source = dict(synthetic=True, dataset_type='raha_flights_v1', files={
        'observed': {'sha256': ev.sha(dirty.read_bytes())}, 'evaluation_reference': {'sha256': ev.sha(reference.read_bytes())}})
    source_path = root/'source.json'; source_path.write_text(json.dumps(source))
    indexed, _ = ev.load_dataset(dirty, source['files']['observed']['sha256'])
    grouped = ev.observed_groups(indexed, 42)
    identifier, time = uuid4().hex, '2026-01-01T00:00:00'
    entries = []
    for group in grouped.groups:
        for field in ev.TIME_FIELDS:
            evidence = ev.investigate_field(group, field)
            entry = dict(discrepancy_id=evidence.discrepancy_id, flight=group.flight, field=field,
                evidence_digest=evidence.evidence_digest, status='unreviewed', resolution=None, decision=None,
                observations=[dict(tuple_id=c.tuple_id, src=c.src, row_number=c.row_number, source_usable=c.source_usable) for c in evidence.claims])
            chosen = (decisions or {}).get((group.flight, field))
            if chosen:
                action, value = chosen
                manual = value if action in ('override','stale') else None
                candidate = evidence.candidates[0] if action in ('accept','reject') else None
                resolution = None
                if action in ('override','stale'):
                    normal = ev.normalize_time(manual)
                    resolution = dict(origin='human_assertion', canonical_clock=normal.canonical_clock, precision=normal.precision,
                                      qualifiers=list(normal.qualifiers), supporting_observation_ids=[], supporting_source_ids=[])
                elif action == 'accept': resolution = ev.candidate_resolution(candidate)
                event = dict(id=uuid4().hex, request_id=uuid4().hex, job_id=42, discrepancy_id=evidence.discrepancy_id,
                    flight=group.flight, field=field, evidence_digest='sha256:'+'0'*64 if action=='stale' else evidence.evidence_digest,
                    revision=1, action='override' if action=='stale' else action, candidate_id=candidate.candidate_id if candidate else None,
                    investigation_id=uuid4().hex if action in ('accept','reject') else None, manual_value=manual, resolution=resolution,
                    rationale='Synthetic reviewer rationale.', reviewer_label='Synthetic local reviewer', policy_version=ev.REVIEW_POLICY,
                    normalization_policy=ev.NORMALIZATION_POLICY, detection_policy=ev.DETECTION_POLICY, created_at=time)
                entry.update(status={'accept':'accepted','override':'overridden','reject':'rejected','unresolved':'unresolved','stale':'stale'}[action],
                             decision=event, resolution=None if action=='stale' else resolution)
            entries.append(entry)
    snapshot = dict(job_id=42, input_sha256=ev.sha(dirty.read_bytes()), contract='raha_flights_v1', contract_version=1,
        export_policy=ev.EXPORT_POLICY, review_policy=ev.REVIEW_POLICY, normalization_policy=ev.NORMALIZATION_POLICY,
        detection_policy=ev.DETECTION_POLICY, fields=entries, unmapped_decisions=[], ungroupable_observations=[
            dict(tuple_id=i.observation.raw.tuple_id, src=i.observation.raw.src, flight=i.observation.raw.flight,
                 row_number=i.observation.raw.row_number, reason=i.reason, fields=list(ev.TIME_FIELDS), issues=[ev.asdict(x) for x in i.observation.raw.issues]) for i in grouped.ungroupable])
    rows, exceptions = {}, []
    for entry in entries:
        row = rows.setdefault(entry['flight'], dict(job_id=42, export_id=identifier, flight=entry['flight']))
        event, field = entry['decision'], entry['field']
        did, rev = (event['id'],event['revision']) if event else ('',0)
        row.update({field: entry['resolution']['canonical_clock'] if entry['resolution'] else '', field+'_status':entry['status'],field+'_decision_id':did,field+'_revision':rev})
        if not entry['resolution']:
            exceptions.append(dict(job_id=42,export_id=identifier,flight=entry['flight'],field=field,discrepancy_id=entry['discrepancy_id'],review_status=entry['status'],reason='stale_review' if entry['status']=='stale' else 'no_human_approved_value',decision_id=did,revision=rev,tuple_id='',src='',row_number=''))
    for item in snapshot['ungroupable_observations']:
        exceptions.append(dict(job_id=42,export_id=identifier,flight=item['flight'],field='',discrepancy_id='',review_status='ungroupable',reason=item['reason'],decision_id='',revision=0,tuple_id=item['tuple_id'],src=item['src'],row_number=item['row_number']))
    def escape(v):
        return "'"+v if isinstance(v,str) and v and (v.startswith("'") or v[0] in '=+-@' or v!=v.lstrip() or any(ord(c)<32 for c in v) or v.startswith('\ufeff')) else v
    def written(columns, records): return csv_bytes(columns,[[escape(row[k]) for k in columns] for row in records])
    data = {'reviewed':written(ev.COLUMNS,rows.values()),'exceptions':written(ev.EXCEPTIONS,exceptions)}
    manifest = dict(export_id=identifier, generated_at=time, snapshot_digest=ev.content_digest(snapshot),snapshot=snapshot,
        artifacts={k:{'sha256':ev.sha(v),'bytes':len(v)} for k,v in data.items()})
    metadata = dict(id=identifier, request_id=uuid4().hex,job_id=42,snapshot_digest=manifest['snapshot_digest'],input_sha256=snapshot['input_sha256'],policy_version=ev.EXPORT_POLICY,created_at=time,artifacts={})
    paths = dict(export_dir=root/'export',metadata_path=root/'metadata.json',dirty_path=dirty,reference_path=reference,synthetic_manifest=source_path)
    for k,v in data.items(): (paths['export_dir']/ev.FILES[k]).write_bytes(v)
    save(paths, manifest, metadata)
    return paths, manifest, metadata


def save(paths, manifest, metadata):
    manifest['snapshot_digest'] = ev.content_digest(manifest['snapshot'])
    metadata['snapshot_digest'] = manifest['snapshot_digest']
    data = {k:(paths['export_dir']/ev.FILES[k]).read_bytes() for k in ('reviewed','exceptions')}
    manifest['artifacts'] = {k:{'sha256':ev.sha(v),'bytes':len(v)} for k,v in data.items()}
    (paths['export_dir']/'provenance.json').write_text(json.dumps(manifest))
    data['provenance'] = (paths['export_dir']/'provenance.json').read_bytes()
    metadata['artifacts'] = {k:{'sha256':ev.sha(v),'bytes':len(v)} for k,v in data.items()}
    paths['metadata_path'].write_text(json.dumps(metadata))


class EvaluationTests(unittest.TestCase):
    def test_repair_categories_detection_units_and_denominators(self):
        decisions = {('ZZ-1-AAA-BBB','sched_dep_time'):('accept',None), ('ZZ-2-AAA-BBB','sched_dep_time'):('override','15:00'), ('ZZ-3-AAA-BBB','sched_dep_time'):('override','15:00')}
        with TemporaryDirectory() as root:
            paths,_,_ = fixture(Path(root),decisions=decisions)
            report = ev.evaluate(**paths,evaluated_at='fixed')
            exact = report['exact_string']; counts=exact['counts']
            for key,value in dict(cells_total=36,original_errors=5,originally_valid=31,approved_cells=6,approved_changes=5,
                corrected_errors=1,harmful_repairs=2,wrong_to_wrong_changes=2,remaining_errors=6,unchanged_valid_cells=29).items():
                self.assertEqual(counts[key],value,key)
            self.assertEqual(exact['repair_precision'],ev.ratio(1,5))
            for key,value in dict(true_positives=1,false_positives=4,false_negatives=2,true_negatives=13,groups_total=20).items():
                self.assertEqual(exact['detection'][key],value,key)
            self.assertEqual(report['coverage']['approved_cells'],ev.ratio(6,36))
            self.assertFalse(report['coverage']['ai_states']['available'])
            self.assertEqual(report,ev.evaluate(**paths,evaluated_at='fixed'))

    def test_unapproved_states_missingness_ungroupable_and_zero_denominators(self):
        for state in ('reject','unresolved','stale',None):
            with self.subTest(state=state),TemporaryDirectory() as root:
                rows=[observation('a','s','ZZ-1-AAA-BBB',''),observation('b','t','','Not Available')]
                targets=copy.deepcopy(rows); targets[0][3]='14:00'
                decisions={('ZZ-1-AAA-BBB','sched_dep_time'):(state,'14:00')} if state else {}
                # A rejected proposal needs an observed candidate; choose another field.
                if state=='reject': decisions={('ZZ-1-AAA-BBB','act_dep_time'):('reject',None)}
                paths,_,_=fixture(Path(root),rows,targets,decisions)
                report=ev.evaluate(**paths)
                self.assertEqual(report['exact_string']['counts']['remaining_errors'],1)
                self.assertIsNone(report['exact_string']['repair_precision']['value'])
                self.assertEqual(report['alignment']['ungroupable_observations'],1)
                self.assertEqual(report['coverage']['approved_cells']['numerator'],0)
                self.assertGreater(report['conservative_semantic']['counts']['outcome_unscorable_cells'],0)

    def test_semantic_equivalence_unknown_precision_and_canonical_approved_clock(self):
        pairs=[('9:22 AM','09:22 a.m.','equal'),('9:22 AM','9:32 AM','different'),('','14:00','unknown'),
            ('Not Available','Not Available','unknown'),('9:22','9:22 AM','unknown'),('9:22 AM (Estimated)','9:22 AM','unknown'),('9:22:00 AM','9:22 AM','unknown')]
        for left,right,result in pairs:
            self.assertEqual(ev.semantic(ev.normalize_time(left),ev.normalize_time(right)),result)
        with TemporaryDirectory() as root:
            rows=[observation('a','s','ZZ-1-AAA-BBB','9:22 AM'),observation('b','t','ZZ-1-AAA-BBB','9:32 AM')]
            targets=copy.deepcopy(rows)
            for row in targets: row[3]='09:22 a.m.'
            paths,_,_=fixture(Path(root),rows,targets,{('ZZ-1-AAA-BBB','sched_dep_time'):('accept',None)})
            result=ev.evaluate(**paths)
            self.assertEqual(result['exact_string']['counts']['corrected_errors'],0)
            self.assertEqual(result['conservative_semantic']['counts']['corrected_errors'],1)
            self.assertEqual(result['conservative_semantic']['counts']['harmful_repairs'],0)
            self.assertEqual(result['conservative_semantic']['counts']['outcome_unscorable_cells'],0)

    def test_tuple_join_and_metric_order_independence(self):
        with TemporaryDirectory() as first,TemporaryDirectory() as second:
            paths,_,_=fixture(Path(first))
            rows,_=ev.decode_flights(paths['dirty_path'].read_bytes())
            clean,_=ev.decode_flights(paths['reference_path'].read_bytes())
            shuffled,_,_=fixture(Path(second),[[r[f] for f in ev.HEADER] for r in reversed(rows)],[[r[f] for f in ev.HEADER] for r in reversed(clean)])
            a,b=ev.evaluate(**paths),ev.evaluate(**shuffled)
            for key in ('exact_string','conservative_semantic','coverage'): self.assertEqual(a[key],b[key])

    def test_alignment_rejects_duplicates_missing_keys_identity_and_contradictory_targets(self):
        for change in ('duplicate','blank','missing','source','flight','contradiction'):
            with self.subTest(change=change),TemporaryDirectory() as root:
                paths,_,_=fixture(Path(root))
                rows,_=ev.decode_flights(paths['reference_path'].read_bytes())
                if change=='duplicate': rows.append(rows[0].copy())
                elif change=='blank': rows[0]['tuple_id']=''
                elif change=='missing': rows.pop()
                elif change in ('source','flight'): rows[0]['src' if change=='source' else 'flight']='different'
                else: rows[0]['act_dep_time']='17:00'
                paths['reference_path'].write_bytes(csv_bytes(ev.HEADER,[[r[f] for f in ev.HEADER] for r in rows]))
                source=json.loads(paths['synthetic_manifest'].read_text()); source['files']['evaluation_reference']['sha256']=ev.sha(paths['reference_path'].read_bytes()); paths['synthetic_manifest'].write_text(json.dumps(source))
                with self.assertRaises(ev.IntegrityError): ev.evaluate(**paths)

    def test_hash_input_policy_mapping_and_approval_corruption_fail_closed(self):
        for change in ('artifact','missing','input','policy','mapping','revision','hidden','candidate','digest','csv'):
            with self.subTest(change=change),TemporaryDirectory() as root:
                paths,manifest,metadata=fixture(Path(root),decisions={('ZZ-1-AAA-BBB','sched_dep_time'):('accept',None)})
                entry=manifest['snapshot']['fields'][0]
                if change=='artifact': (paths['export_dir']/'reviewed.csv').write_bytes(b'changed')
                elif change=='missing': (paths['export_dir']/'exceptions.csv').unlink()
                else:
                    if change=='input': metadata['input_sha256']='0'*64
                    elif change=='policy': manifest['snapshot']['export_policy']='unsupported'
                    elif change=='mapping': entry['observations'].append(entry['observations'][0])
                    elif change=='revision': entry['decision']['revision']=0
                    elif change=='hidden': entry['status']='unreviewed'
                    elif change=='candidate': entry['decision']['candidate_id']='foreign'
                    elif change=='digest': entry['evidence_digest']='sha256:'+'0'*64
                    elif change=='csv': (paths['export_dir']/'reviewed.csv').write_bytes((paths['export_dir']/'reviewed.csv').read_bytes().replace(b'accepted',b'unreviewed'))
                    save(paths,manifest,metadata)
                with self.assertRaises((ev.IntegrityError,OSError)): ev.evaluate(**paths)

    def test_wrong_dirty_dataset_and_no_synthetic_impersonation(self):
        with TemporaryDirectory() as root:
            paths,_,_=fixture(Path(root))
            with self.assertRaises(ev.IntegrityError): ev.evaluate(**{k:v for k,v in paths.items() if k!='synthetic_manifest'})
            paths['dirty_path'].write_bytes(paths['dirty_path'].read_bytes()+b'\n')
            with self.assertRaises(ev.IntegrityError): ev.evaluate(**paths)

    def test_cli_isolated_imports_atomic_output_and_no_input_modification(self):
        with TemporaryDirectory() as root,TemporaryDirectory() as outputs:
            paths,_,_=fixture(Path(root))
            before={p:ev.sha(p.read_bytes()) for p in Path(root).rglob('*') if p.is_file()}
            command=[sys.executable,'-B',str(Path(ev.__file__)), '--export-dir',str(paths['export_dir']), '--metadata',str(paths['metadata_path']),
                     '--dirty',str(paths['dirty_path']),'--reference',str(paths['reference_path']),'--synthetic-manifest',str(paths['synthetic_manifest']), '--output',str(Path(outputs)/'evaluation.json')]
            result=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['benchmark_kind'],'synthetic')
            self.assertNotEqual(subprocess.run(command,capture_output=True,timeout=10).returncode,0)
            self.assertEqual(before,{p:ev.sha(p.read_bytes()) for p in before})
            guard="""import sys
class Guard:
 def find_spec(self,name,*args):
  if name.startswith(('app.core','app.models','app.main','app.reconciliation.ai','app.reconciliation.review','app.reconciliation.investigations','openai','sqlmodel','fastapi')): raise RuntimeError('runtime import forbidden')
sys.meta_path.insert(0,Guard())
sys.path.insert(0,'scripts')
import evaluate_flights
assert not any(n.startswith(('app.core','openai','fastapi','sqlmodel')) for n in sys.modules)
"""
            check=subprocess.run([sys.executable,'-B','-c',guard],cwd=ev.REPOSITORY,capture_output=True,text=True,timeout=10)
            self.assertEqual(check.returncode,0,check.stderr)

    def test_invalid_freeze_is_rejected_before_reference_access(self):
        from unittest.mock import patch
        with TemporaryDirectory() as root:
            paths,manifest,metadata=fixture(Path(root))
            manifest['snapshot']['fields'][0]['observations'].append(manifest['snapshot']['fields'][0]['observations'][0])
            save(paths,manifest,metadata)
            paths['reference_path'].unlink()
            with patch.object(ev,'load_dataset',wraps=ev.load_dataset) as loader:
                with self.assertRaisesRegex(ev.IntegrityError,'observation_mapping'): ev.evaluate(**paths)
                self.assertEqual(loader.call_count,1)  # Dirty data only.

    def test_semantic_joint_cohort_and_precision_exclusions(self):
        with TemporaryDirectory() as root:
            rows=[observation('a','s','ZZ-1-AAA-BBB','13:00'),observation('b','t','ZZ-1-AAA-BBB','13:00')]
            target=copy.deepcopy(rows)
            for row in target: row[3]='14:00'
            paths,_,_=fixture(Path(root),rows,target,{('ZZ-1-AAA-BBB','sched_dep_time'):('override','14:00:00')})
            report=ev.evaluate(**paths)
            semantic=report['conservative_semantic']
            self.assertEqual(semantic['original_reference']['different'],2)
            self.assertEqual(semantic['counts']['original_errors'],0)  # Joint-cohort count, explicitly separate.
            self.assertEqual(semantic['counts']['outcome_unscorable_cells'],2)
            self.assertEqual(semantic['exclusions']['final_reference_incompatible_precision_or_qualifiers'],2)
            self.assertEqual(report['exact_string']['counts']['wrong_to_wrong_changes'],2)

    def test_duplicate_json_and_output_or_symlink_redirection_are_rejected(self):
        with TemporaryDirectory() as root:
            paths,_,_=fixture(Path(root))
            with self.assertRaises(ev.IntegrityError): ev.write_report(paths['export_dir']/'report.json',{},list(paths.values()))
            reference=paths['reference_path']
            saved=reference.with_suffix('.real'); reference.rename(saved); reference.symlink_to(saved)
            with self.assertRaises(ev.IntegrityError): ev.evaluate(**paths)
            reference.unlink(); saved.rename(reference)
            content=paths['metadata_path'].read_text()
            paths['metadata_path'].write_text(content[:-1]+',"id":"duplicate"}')
            with self.assertRaisesRegex(ev.IntegrityError,'duplicate_json_key'): ev.evaluate(**paths)


if __name__=='__main__': unittest.main()
