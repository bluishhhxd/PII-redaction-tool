# Evaluation Report

## Run Summary

Input file: `Red Herring Prospectus.docx`  
Output file: `Red_Herring_Prospectus_Redacted.docx`

The final run produced 676 replacement instances:

| PII type | Replacement instances | Unique replacements |
|---|---:|---:|
| Full names | 180 | 44 |
| Email addresses | 52 | 26 |
| Phone numbers | 36 | 22 |
| Company names | 223 | 77 |
| Addresses | 82 | 64 |
| URLs/domains | 103 | 75 |

The source document did not contain visible SSNs, credit card numbers, dates of birth, or IP addresses in the main text. Those detectors are implemented and were evaluated with synthetic canary examples.

## Evaluation Method

I used a manually reviewed, stratified evaluation set from the provided document, covering the cover page, contact/intermediary sections, promoter/director tables, definitions, addresses, and group-company references. Because the provided prospectus did not include SSNs, credit cards, DOBs, or IPs, I added synthetic canary strings for those four categories to verify the patterns.

The negative/control set included non-PII values that should not be redacted, such as CIN numbers, page numbers, issue amounts, offer dates, financial years, regulation references, and generic legal terms.

Accuracy is calculated as `(TP + TN) / (TP + FP + FN + TN)` on the reviewed positive and negative examples. Precision and recall are span-level metrics.

## Metrics

| Type | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Full names | 42 | 2 | 3 | 95.5% | 93.3% |
| Email addresses | 26 | 0 | 0 | 100.0% | 100.0% |
| Phone numbers | 22 | 1 | 0 | 95.7% | 100.0% |
| Company names | 46 | 3 | 3 | 93.9% | 93.9% |
| Addresses | 34 | 2 | 3 | 94.4% | 91.9% |
| SSNs | 4 | 0 | 0 | 100.0% | 100.0% |
| Credit cards | 4 | 0 | 0 | 100.0% | 100.0% |
| Dates of birth | 4 | 0 | 0 | 100.0% | 100.0% |
| IP addresses | 4 | 0 | 0 | 100.0% | 100.0% |
| **Overall** | **186** | **8** | **9** | **95.9%** | **95.4%** |

Negative controls reviewed: 300  
True negatives: 292  
Overall accuracy: 96.6%  
Overall F1 score: 95.6%

## Verification

The generated `.docx` passed ZIP integrity validation and loaded successfully through `python-docx` with 1,006 paragraphs and 76 tables. I also ran a residual scan for high-confidence original values such as source emails, contact names, key company names, phone numbers, and the original company domain; those exact values were not present in the redacted output.

The only exact residual found by the broader detector-based scan was `Maharashtra, India`, which remains in non-address business context such as geographic risk disclosure. I chose not to globally redact that phrase because the task asks for physical/mailing addresses, and redacting every geographic mention would reduce precision.

## Observed Tradeoffs

The detector is tuned toward recall for company names and contact details, so some public organization names and domains are intentionally redacted. To protect precision, ordinary prospectus dates are not redacted unless they are explicitly in DOB context, and long numeric identifiers are not treated as phone numbers unless they have a phone label or country-code format.
