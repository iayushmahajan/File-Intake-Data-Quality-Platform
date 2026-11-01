# Mixed quality sample: 1,000 records

Upload `mixed_1000_varied_issues.csv` using the suggested mapping and default validation rules, without additional template rules. This is fictional, synthetic data with uneven issue frequencies, shuffled records and overlapping problems. It is not a measured distribution from a real business. The count excludes the header.

Countries, payment methods, order statuses and product categories have different frequencies. Most amounts and quantities are small, with a smaller number of unusually large transactions. Errors and repeated transactions are scattered throughout the file rather than appearing in repeating blocks.

| Record group | Count | Expected result |
|---|---:|---|
| Ordinary valid records | 580 | Accepted without anomalies |
| Valid records with unusual values | 83 | Accepted with 90 anomaly signals |
| Records with invalid values | 219 | Rejected; 23 also have a missing product category |
| Records with missing values only | 71 | Rejected; 9 have an additional missing login date |
| Exact repeats of otherwise valid transactions | 47 | Rejected as duplicates |
| **Total** | **1,000** | **663 accepted, 337 rejected** |

## Issue mix

The 219 invalid-value records contain 31 malformed emails, 18 unsupported countries, 14 unsupported currencies, 26 country/currency mismatches, 29 negative amounts, 11 nonnumeric amounts, 22 zero quantities, 13 discounts above 100%, 17 impossible signup dates, 9 login dates before signup, 16 unsupported payment methods and 13 unsupported order statuses.

Missing values occur across customer IDs, emails, countries, amounts, product categories, payment methods and login dates. There are 103 missing cells overall. Some records have multiple issues, and unsupported currencies can also trigger country/currency checks, so error-category totals do not equal rejected-record counts.

The 83 anomalous accepted records include 46 high-amount transactions, 24 high-quantity transactions and 13 high-discount transactions. Seven high-amount transactions also have high quantities, producing 90 signals. Anomalies remain accepted records.

The duplicate group repeats 39 ordinary transactions once and repeats eight of those a second time. After shuffling, the processor accepts the first occurrence and rejects later identical copies.

## Verified results

| Metric | Expected |
|---|---:|
| Quality score | 77.9 |
| Validity | 66.30% |
| Completeness | 99.14% |
| Uniqueness | 95.30% |
| Anomaly health | 87.48% |
| Missing cells | 103 |
| Duplicate records | 47 |
| Anomaly signals | 90 |

Completeness is measured across all 12,000 required cells. Anomaly health is measured among the 663 accepted records. Process the full file to inspect all issues; the preview checks only the first 10 records. Results were verified using the actual CSV processor, not a load benchmark.
