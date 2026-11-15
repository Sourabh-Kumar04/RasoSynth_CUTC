# RasoSynthTune Dataset Contract & Statutory Grounding Specification

Normative technical contract defining dataset states, dynamic statutory grounding schemas, cryptographic provenance hashing, and statutory PII checksum verification rules.

---

## 1. Core State Definitions & Evidence Contract

A dataset must satisfy explicit mathematical and audit conditions before receiving state badges. Labels must never be derived from job completion alone.

### 1.1 Certified
* **Normative Definition**: A dataset that has completed synthesis, deduplication, quality gate scoring, and human-in-the-loop review (where configured), sealed with a cryptographic SHA-256 Merkle root. Any token alteration invalidates the seal.
* **Audit Rule**: Badges in UI and API responses must be verified by recomputing the leaf hashes over exported samples. Datasets with unverified seals must be marked `unverified` or `legacy`.

### 1.2 Validated
* **Normative Definition**: A dataset whose samples conform to the target schema (e.g. instruction/input/response), exceed defined domain quality thresholds, pass exact and MinHash semantic deduplication, and pass statutory PII detection with mathematical checksum validation.
* **Audit Rule**: Validation results must be recorded in the persistent metadata record per dataset. `job.status === 'completed'` does not qualify as validated evidence.

### 1.3 Ready
* **Normative Definition**: A dataset that is simultaneously Validated, Sealed (with an In-Toto signed DBOM bundle), and Exported in a consumable training format (JSONL, Parquet, or Hugging Face Dataset format).
* **Audit Rule**: Datasets are marked `Ready` only when validation evidence, Merkle proof, and accessible file paths are all confirmed.

---

## 2. Dynamic Statutory Grounding & Citation Schema

For regulatory, taxation, legal, and compliance datasets, every sample must adhere to the Statutory Grounding Schema to prevent hallucinations and enforce legal auditability.

### 2.1 Sample Schema Fields
| Field Name | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `instruction` | string | Yes | Prompt or query formulating the domain task. | `"What are the ITC conditions under Section 16(2)?"` |
| `response` | string | Yes | Authoritative, legally grounded answer. | `"Under Section 16(2) of the CGST Act 2017..."` |
| `input` | string | No | Optional context or source passage. | `""` |
| `citation` | string | Yes | Authoritative section, rule, or circular citation. | `"Section 16(2) CGST Act 2017 read with Rule 36(4)"` |
| `statutory_references`| list[string]| Yes | List of statutory sections referenced. | `["Section 16(2) of CGST Act 2017", "Rule 36(4)"]` |
| `circular_id` | string | No | Official Gazette notification or circular ID. | `"Notification No. 10/2023-CT"` |
| `issuing_authority` | string | Yes | Regulating statutory body. | `"Central Board of Indirect Taxes and Customs (CBIC)"` |
| `date_issued` | string | No | Date of issuance (ISO 8601 or Gazette format). | `"2023-05-10"` |
| `effective_date` | string | Yes | Legal enforcement date (ISO 8601: `YYYY-MM-DD`). | `"2023-08-01"` |
| `verified_statutory` | boolean | Yes | Explicitly audited against official gazette text. | `true` |

### 2.2 Canonical Issuing Authorities
Grounding fields must reference recognized statutory and regulatory bodies:
* `Central Board of Indirect Taxes and Customs (CBIC)`
* `Central Board of Direct Taxes (CBDT)`
* `Reserve Bank of India (RBI)`
* `Ministry of Corporate Affairs (MCA)`
* `Data Protection Board of India (DPBI)`
* `Ministry of Electronics and Information Technology (MeitY)`

---

## 3. Cryptographic Provenance & DBOM Integrity

### 3.1 Deterministic Sample Leaf Hash
The leaf hash covers **only** immutable semantic content: `instruction`, `response`, `input`, and domain `metadata`. Storage-assigned identifiers (`id`, `dataset_id`, `created_at`) and volatile scoring tiers are strictly excluded.

$$\text{LeafHash} = \text{SHA-256}\left(\text{JSON}_{\text{canonical}}\left(\{\text{instruction}, \text{response}, \text{input}, \text{metadata}\}\right)\right)$$

Canonical JSON formatting rules:
1. Keys sorted alphabetically (`sort_keys=True`).
2. Compact delimiters without whitespace: separators `(',', ':')`.
3. UTF-8 character encoding (no ASCII escaping of Indic scripts).

### 3.2 Merkle Tree Assembly
Leaf hashes are pairwise hashed from left to right. When a level contains an odd number of nodes, the final node is duplicated to balance the pair:

$$\text{ParentNode} = \text{SHA-256}\left(\text{LeftHash} \,\|\, \text{RightHash}\right)$$

### 3.3 Supply-Chain Attestation
Final datasets are sealed into an **in-toto v1.0 Statement** bundle signed using **ECDSA SECP256R1** to produce tamper-evident artifacts.

---

## 4. Statutory PII & Checksum Validation Contract

Pattern matching alone is insufficient for statutory compliance. The pipeline enforces structural checksum validation across personal and financial identifiers.

```
       Candidate Match (Regex / NER)
                    │
                    ▼
       ┌─────────────────────────┐
       │ Identifier Type Lookup  │
       └────────────┬────────────┘
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
[Aadhaar]         [PAN]           [GSTIN]
Verhoeff D8      Category         Mod-36
Dihedral Check   Validation       Check Digit
   │                │                │
   └────────────────┼────────────────┘
                    │
                    ▼
         Valid Statutory Identity
         Action: Redact or Mask
```

### 4.1 Aadhaar Numbers (UIDAI)
* **Format**: 12-digit number (pattern `[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}`).
* **Checksum Algorithm**: **Verhoeff Dihedral Group ($D_8$) Algorithm**.
* **Validation Rule**: Evaluated left to right across permutation table $P$ and multiplication table $D$. Must resolve to checksum identity $c = 0$. Numbers failing the Verhoeff check are treated as non-Aadhaar numeric artifacts.

### 4.2 Permanent Account Numbers (PAN)
* **Format**: 10-character alphanumeric string (`[A-Z]{5}[0-9]{4}[A-Z]`).
* **Holder-Category Check**: The 4th character must match a valid legal entity category:
  * `P`: Individual
  * `C`: Company
  * `H`: Hindu Undivided Family (HUF)
  * `F`: Firm / Limited Liability Partnership
  * `A`: Association of Persons (AOP)
  * `T`: Trust
  * `B`: Body of Individuals (BOI)
  * `L`: Local Authority
  * `J`: Artificial Juridical Person
  * `G`: Government Agency

### 4.3 Goods & Services Tax Identification Numbers (GSTIN)
* **Format**: 15-character alphanumeric identifier (`[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}`).
* **Structural Check**:
  1. Digits 1–2: Valid State/UT Code (range `01` to `37`, `97`, `99`).
  2. Characters 3–12: Valid PAN of the registered entity.
  3. Character 13: Entity registration number within state (`1-9`, `A-Z`).
  4. Character 14: Default statutory constant `Z`.
  5. Character 15: Mod-36 check digit computed over the initial 14 characters.

### 4.4 Redaction & Replacement Protocol
Identified statutory PII must be sanitized using one of two non-reversible modes:
* **Redact Mode**: Explicitly replaced with type-safe semantic tokens: `[AADHAAR_REDACTED]`, `[PAN_REDACTED]`, `[GSTIN_REDACTED]`, `[MOBILE_REDACTED]`.
* **Synthetic Mask Mode**: Replaced with synthetically generated test values that intentionally pass structural checksums but use allocated test-range prefixes.

---

## 5. Non-Negotiable Pipeline Rules

1. **One Dataset, One Metric Source**: Discrepancies between UI dashboard metrics and database records invalidate dataset certification until re-indexed from raw records.
2. **Deterministic DBOM Seal**: A DBOM seal binds the exact exported byte stream. Any subsequent human review edit or post-processing invalidates the seal and triggers a mandatory re-attestation.
3. **Fail-Closed Compliance**: When compliance tests are not explicitly executed, reports must state `not_measured` or `unverified`. Defaulting to `compliant` or `zero_risk` is strictly prohibited.
