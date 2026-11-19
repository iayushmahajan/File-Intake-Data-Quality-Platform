# Manual test files

Upload these files individually through the dashboard. Expected counts and scores were checked with the CSV processor.

| File | Expected result | Accepted / rejected | Score |
|---|---|---|---:|
| `01_all_valid.csv` | Completed | 3 / 0 | 100 |
| `02_mixed_results.csv` | Completed with row errors | 2 / 1 | 80 |
| `03_all_invalid.csv` | Completed with all rows rejected | 0 / 2 | 33.3 |
| `04_duplicate_records.csv` | Completed; second identical record rejected | 2 / 1 | 76.7 |
| `05_bom_multiline.csv` | Completed; quoted comma/newline and UTF-8 BOM parsed correctly | 2 / 0 | 100 |
| `06_missing_columns.csv` | Failed with missing-column explanation | 0 / 0 | — |
| `07_header_only.csv` | Failed because there are no data records | 0 / 0 | — |
| `08_wrong_type.txt` | Upload rejected; no job created | — | — |

A completed job means the file was processed, not that every row passed. All-invalid data can still receive completeness/uniqueness credit; check the accepted count alongside the score.

For anomaly review, upload `../anomaly_demo.csv`: expect 4 accepted records, 0 rejected, 3 anomaly signals and a 92.5 score. Anomaly signals do not reject records.

## Quick checks

1. Upload `01_all_valid.csv`. Results should appear automatically; small files may finish between status polls.
2. Download clean/error CSVs and compare counts with the table. Preview `05_bom_multiline.csv`; the quoted newline should stay within one logical record.
3. Refresh the page and reopen a job from history. Counts, score and analytics should persist.
4. Search by filename and filter completed/failed jobs. Preview the original and output files.
5. Upload the invalid-structure and wrong-type files. Check the visible error and whether a job was created as described above.
6. Optional: with no AI key configured, request AI insights. A configuration message should appear while ordinary analytics and downloads remain usable.

## Check queued processing

From the repository root, stop only the worker:

```bash
docker compose stop worker
```

Upload a valid file. It should remain pending/queued. Refresh the browser, then promptly restart the worker (the default queue timeout is 10 minutes):

```bash
docker compose start worker
```

The same job should complete automatically. To exercise restarts, broker outages and duplicate delivery in disposable infrastructure, use `backend/.venv/bin/python scripts/verify_async_stack.py` instead of disrupting development jobs.


## Mapped import and correction walkthrough

Upload `09_partner_headers.csv`. Confirm the suggested title-case header mapping, save a template named **Partner transactions**, preview, then process. Expect **1 accepted / 1 rejected**, score **70**. In Dataset explorer select **Correct record 3**, change `email` to `bob@example.com`, validate and reprocess. Expect a linked child job with **2 accepted / 0 rejected**, score **100**. Reopen the parent to confirm its original results and files remain unchanged. Select the saved template on a second import to verify reuse.

Use the explorer's error category and status filters and download **Export filtered CSV** to verify the export matches the selected result set. More configuration and correction details are in [the transaction compatibility reference](../../../docs/RECONCILIATION.md#transaction-compatibility).
