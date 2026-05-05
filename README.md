# SecureDoc AI

**Policy-Aware Hybrid AI Document Classification System for Egyptian Banking**

> **Author:** Noor Elhemaly (202300013)
> **Advisor:** Dr. Haitham Ghalwash
> **University:** Coventry University — The Knowledge Hub
> **Regulatory Alignment:** Egypt PDPL No. 151/2020 · CBE Information Security Framework · Banking Law No. 194/2020 Art. 97 · NIST FIPS 204 · ISO 27001:2022

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Classification System](#classification-system)
5. [Security Rules Engine](#security-rules-engine)
6. [5-Stage Processing Pipeline](#5-stage-processing-pipeline)
7. [Post-Quantum Cryptography (PQC)](#post-quantum-cryptography-pqc)
8. [Digital Signatures](#digital-signatures)
9. [OCR: Qwen2.5-VL & Tesseract](#ocr-qwen25-vl--tesseract)
10. [Blockchain Audit Trail](#blockchain-audit-trail)
11. [Confidence Scoring](#confidence-scoring)
12. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
13. [REST API Reference](#rest-api-reference)
14. [Frontend Interface](#frontend-interface)
15. [Configuration & Users](#configuration--users)
16. [Demo Documents & Dataset](#demo-documents--dataset)
17. [Storage Structure](#storage-structure)
18. [Installation & Setup](#installation--setup)
19. [Running the Application](#running-the-application)
20. [Benchmarking & Testing](#benchmarking--testing)
21. [Known Issues & Fixes](#known-issues--fixes)
22. [Regulatory Compliance](#regulatory-compliance)

---

## Overview

SecureDoc AI is a full-stack, AI-powered document classification and protection system built specifically for the Egyptian banking sector. It combines a hybrid LLaMA 3 + regex rules classification engine with post-quantum encryption, blockchain audit trails, digital signatures, and role-based access control to ensure documents are classified, encrypted, and accessed according to policy and regulatory requirements.

**Core capabilities:**

- Hybrid AI classification (LLaMA 3 via Ollama + regex security rules) → 4-level sensitivity labels (C0–C3)
- Post-quantum encryption of sensitive documents (CRYSTALS-Kyber-768 + AES-256-GCM)
- Immutable blockchain audit trail with Merkle tree verification
- Post-quantum digital signatures (CRYSTALS-Dilithium3 / ML-DSA-65)
- Multi-language OCR (Arabic + English) via Qwen2.5-VL and Tesseract
- Role-based access control with 5 user levels and field-level redaction
- Compliance with Egypt PDPL, CBE Information Security Framework, and NIST FIPS 204

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              React + TypeScript Frontend (Vite)             │
│                     http://localhost:5173                    │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST (CORS)
┌────────────────────────────▼────────────────────────────────┐
│                   Flask API (web_api.py)                     │
│                     http://localhost:5001                    │
└──┬───────────┬──────────────┬───────────────┬───────────────┘
   │           │              │               │
   ▼           ▼              ▼               ▼
main_pipeline  rbac_system  audit_trail  pqc_encryption
security_rules  pdf_extractor  qwen_ocr  digital_signature
confidence_scoring  blockchain_protection  redaction
                             │
              ┌──────────────▼───────────────┐
              │   Ollama LLM  (localhost:11434)│
              │   LLaMA 3 / llama3            │
              └──────────────────────────────┘
```

**Backend:** Python 3.8+ · Flask · REST API on port 5001
**Frontend:** React 18.3 · TypeScript · Vite 6.3 · Tailwind CSS · Recharts
**LLM:** LLaMA 3 via Ollama (local inference, no external API calls)
**OCR:** Qwen2.5-VL-3B-Instruct (primary) · Tesseract (fallback)
**Encryption:** CRYSTALS-Kyber-768 + AES-256-GCM
**Signatures:** CRYSTALS-Dilithium3 (ML-DSA-65)

---

## Project Structure

```
SecureDoc AI/
├── web_api.py                                    # Flask REST API (2,973 lines)
├── src/
│   ├── main_pipeline.py                          # Core 5-stage processing pipeline (1,902 lines)
│   ├── security_rules.py                         # Regex pattern classification engine (904 lines)
│   ├── rbac_system.py                            # Role-based access control (370 lines)
│   ├── pqc_encryption.py                         # Kyber-768 + AES-256-GCM encryption
│   ├── digital_signature.py                      # CRYSTALS-Dilithium3 signatures
│   ├── qwen_ocr.py                               # Qwen2.5-VL vision-language OCR
│   ├── pdf_extractor.py                          # PDF & image text extraction
│   ├── audit_trail.py                            # Blockchain audit logging
│   ├── blockchain_protection.py                  # Document content protection chain
│   ├── confidence_scoring.py                     # Multi-factor confidence calculation
│   ├── benchmark.py                              # A/B testing & performance benchmarking
│   ├── signature_benchmark.py                    # Signature performance testing
│   ├── redaction.py                              # Field-level data redaction
│   ├── flag_manager.py                           # CISO document flagging system
│   └── calculate_specificity.py                  # Classification metric utilities
│
├── AI Document Classification Interface/         # React + TypeScript frontend
│   ├── src/
│   │   ├── main.tsx                              # React entry point
│   │   └── app/
│   │       ├── App.tsx                           # Root application component
│   │       ├── context/
│   │       │   ├── AuthContext.tsx               # Auth state & user management
│   │       │   └── SettingsContext.tsx           # Pipeline settings state
│   │       └── components/
│   │           ├── LoginPage.tsx                 # Login form
│   │           ├── Dashboard.tsx                 # Stats & overview
│   │           ├── UploadView.tsx                # File upload with OCR tracking
│   │           ├── HistoryView.tsx               # Document history & search
│   │           ├── DocumentViewer.tsx            # Document detail view
│   │           ├── AuditTrailView.tsx            # Blockchain events viewer
│   │           ├── SettingsView.tsx              # Pipeline configuration
│   │           ├── PipelineStepsView.tsx         # 5-stage pipeline diagram
│   │           ├── VerificationView.tsx          # Signature & integrity checks
│   │           ├── SecurityBadge.tsx             # C0/C1/C2/C3 badge
│   │           ├── Navigation.tsx                # Top navigation menu
│   │           ├── StatCard.tsx                  # Dashboard statistics card
│   │           └── ui/                           # Radix UI component library (30+ primitives)
│   ├── package.json
│   ├── vite.config.ts
│   └── dist/                                     # Built frontend (production)
│
├── config/
│   ├── users.json                                # 13 demo users with credentials & roles
│   └── pqc_encryption_keys.json                  # PQC key metadata index
│
├── storage/
│   ├── secure_storage/                           # Encrypted C2/C3 documents (JSON)
│   ├── audit_logs/                               # Blockchain & audit trail files
│   │   ├── blockchain.json                       # Main audit blockchain
│   │   ├── protection_chain.json                 # Document protection blockchain
│   │   ├── audit_YYYY-MM-DD.jsonl                # Daily timestamped audit logs
│   │   ├── pending_events.json                   # Events awaiting blockchain mining
│   │   └── protection_pending.json               # Protection chain pending events
│   ├── keys/
│   │   ├── pqc_keys/                             # Kyber-768 keypairs (one per document)
│   │   └── signature_keys/                       # Dilithium3 keypairs
│   └── original_files/                           # Uploaded PDFs/images (for watermarking)
│
├── models/
│   ├── bart-large-mnli/                          # BART zero-shot classification model
│   └── .cache/huggingface/                       # Qwen2.5-VL model cache (~7GB)
│
├── demo_documents/                               # 151 demo PDFs (Egyptian banking context)
│   ├── C0/   (39 docs)                           # Public documents
│   ├── C1/   (36 docs)                           # Internal documents
│   ├── C2/   (32 docs)                           # Confidential documents
│   ├── C3/   (35 docs)                           # Highly sensitive documents
│   └── Account_Opening/ (24 docs)                # KYC & account opening forms
│
├── dataset_ground_truth.csv                      # Ground truth labels for demo dataset
├── dataset_ground_truth.json                     # JSON version of ground truth
└── docs/
    └── Digital_Signature_Comparison_Report.pdf  # Benchmark comparison report
```

---

## Classification System

Documents are assigned one of four sensitivity levels based on content analysis:

### C0 — Public

No personal data. Intended for public distribution. No access restrictions.

**Examples:** Press releases, job postings, product brochures, interest rate tables, published annual reports, investor relations materials, CBE regulatory disclosures issued to the public, sustainability & governance reports, holiday notices.

### C1 — Internal

Bank employees only. No personal data. Operational / administrative information.

**Examples:** Internal policies, procedures, training schedules (Q1/Q2 training programmes), IT alerts & security bulletins, internal memos (staff first names acceptable), staff meeting minutes, operations bulletins, compliance statements, internal circulars.

### C2 — Confidential

Two independent classification paths trigger C2:

- **Path A (Personal Data):** Full name combined with any of: email address, phone number, home address, salary range, or employment terms.
- **Path B (Business Confidential):** Vendor contracts, proprietary strategy, audit reports, M&A information, pricing data, legal correspondence, external party involvement (vendors, law firms, regulators, third-party contracts).

**Examples:** Job offer letters, employment contracts, vendor agreements, service contracts, individual employment records, internal audit memos, market analysis reports.

### C3 — Highly Sensitive

Regulated personal or financial data that triggers direct regulatory liability under Egypt PDPL Art. 21 and the CBE Information Security Framework. Any single trigger classifies the entire document as C3.

| Trigger | Pattern |
|---------|---------|
| Egyptian National ID | 14-digit number starting with 2 or 3 |
| Passport number | `[A-Z]{1,2}\d{7,8}` in passport context |
| Egyptian IBAN | `EG` + 27 digits |
| Bank account number | `ACCOUNT NO.` + 6–16 digits |
| Credit card number | 16-digit card format |
| Exact salary amount | `salary: EGP XXXXX` (not a range) |
| Customer risk rating | High/Medium/Low risk in customer context |
| Sanctions screening result | World-Check, OFAC references |
| Source of funds declaration | AML-related disclosures |
| PEP designation | Politically Exposed Person identification |

**Examples:** Payroll records, loan applications, KYC forms, credit assessments, account statements, Suspicious Activity Reports (SAR), identity verification documents.

---

## Security Rules Engine

**File:** `src/security_rules.py` (904 lines)

The rules engine applies regex pattern matching and keyword analysis in parallel with the LLM to provide hard, evidence-based classification signals.

### C3 Hard Triggers (Regulatory PII & Financial Data)

```python
# Egyptian National ID — 14 digits starting with 2 or 3
r'\b[23]\d{13}\b'

# Egyptian IBAN
r'\bEG\d{27}\b'

# Bank Account Number
r'\bACCOUNT\s*(?:NUMBER|NO\.?)\s*[:\s]*\d{6,16}\b'

# Credit Card
r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'

# Exact Salary (not a range)
r'\bsalary\s*(?:amount|:)\s*\d{4,6}'  # + EGP context

# Passport
r'\bpassport\b.*?[A-Z]{1,2}\d{7,8}'

# AML / KYC
r'\b(high|medium|low)\s+risk\b'       # in customer context
r'\bworld.?check\b'
r'\bsanctions.?screening\b'
r'\bsource\s+of\s+funds\b'
r'\bpep\b'                            # Politically Exposed Person
```

### C2 Triggers (Business Confidential)

- External party involvement: vendors, law firms, regulators, third-party contracts
- Proprietary business info: strategy, budget, M&A, audit findings, pricing
- Personal data with contact details: full name + email/phone/address/salary range

### C1 Triggers (Internal)

- Staff-only markers: "for internal use", "internal memo", "internal circular"
- Training schedules: "Q1 training", "training programme"
- Staff meetings, operations bulletins
- Governance signals that are NOT public (annual reports overridden to C0 if published)

### C0 Triggers (Public)

- Press releases, public announcements
- Job postings on public boards
- Product brochures, published interest rates, holiday notices
- Published sustainability & governance reports
- CBE circulars issued for public

### Special Cases

| Scenario | Classification |
|----------|---------------|
| Empty form / template (no real data) | C1 |
| Masked / redacted values | Downgrade to C2 (data not visible) |
| Aggregate financial data (no customer-specific info) | C0 |
| Salary range (not exact) | C2 (not C3) |
| Staff first names only (no ID/contact data) | C1 |

---

## 5-Stage Processing Pipeline

**File:** `src/main_pipeline.py` (1,902 lines)

### Stage 1: Hybrid AI Classification

1. **Text extraction** — PyMuPDF for embedded text; Qwen2.5-VL / Tesseract for scanned/image PDFs
2. **Security rules** — Regex engine scans for C3/C2/C1/C0 patterns, returns triggers and suggested level
3. **LLaMA 3 via Ollama** — Sends full document text with a 270+ line system prompt covering Egyptian banking classification guidelines, PDPL/CBE legal basis, decision flowchart, and examples
4. **Hybrid decision tree** — Resolves agreement/disagreement between rules and LLM:
   - Hard PII triggers (National ID, IBAN, etc.) always win → escalate or confirm C3
   - LLM handles semantic business-confidential documents
   - Confidence scoring on agreement strength
5. **Fallback** — If Ollama unavailable, keyword-based classification is used

**LLM System Prompt (270+ lines):** Defines C0/C1/C2/C3 for Egyptian banking, references PDPL Law 151/2020, CBE Information Security Framework, includes regex patterns, classification examples, decision flowchart, and confidence guidance.

### Stage 2: PQC Encryption (C2 and C3 only)

- Hybrid encryption: CRYSTALS-Kyber-768 key encapsulation + AES-256-GCM symmetric cipher
- Each document receives a unique Kyber-768 keypair
- Shared secret derived via SHA-256 from Kyber ciphertext
- C0/C1 stored as plaintext; C2/C3 encrypted before storage

### Stage 3: Secure Storage

- Stored as JSON in `storage/secure_storage/{doc_id}.json`
- Metadata includes: classification (final, LLM, rules), confidence, triggers, CDE (Critical Data Elements), document type, process, stage, user info, and timestamp
- C2/C3: stores encrypted ciphertext + encapsulated Kyber key + AES nonce

### Stage 3.5: Document Protection (Optional)

- Independent blockchain records a SHA-256 content hash for every document
- Merkle tree of events per block with proof-of-work mining (difficulty 2)
- Detects post-storage tampering via hash mismatch on verification
- Storage: `storage/audit_logs/protection_chain.json`

### Stage 3.5b: Digital Signatures (Optional)

- Signs document content + classification metadata using CRYSTALS-Dilithium3
- Signature stored: `storage/signatures/{doc_id}.json`
- Non-repudiation for PDPL compliance
- Enabled via `enable_digital_signature=True` pipeline flag

### Stage 4: Access Control (RBAC)

- Role-based access check: user level vs. classification level
- Department-aware: C2/C3 users must be in same department (CISO/DPO exempt)
- Field-level redaction applied based on access level
- C2/C3: decryption only for authorized users
- All access attempts (granted or denied) logged to audit trail

### Stage 5: Audit Trail Verification

- Merkle root verification for every block
- Full chain integrity check (hash chaining)
- Blockchain events written to `storage/audit_logs/blockchain.json`
- Pending events persisted in `storage/audit_logs/pending_events.json` (survives restarts)

---

## Post-Quantum Cryptography (PQC)

**File:** `src/pqc_encryption.py`

### Algorithm: Hybrid CRYSTALS-Kyber-768 + AES-256-GCM

**Security Level:** NIST Level 3 (128-bit quantum security). Resistant to Shor's algorithm on quantum computers. NIST 2024 approved algorithm.

### Encryption Flow

```
1. Generate Kyber-768 keypair (unique per document)
2. Encapsulate shared secret via Kyber public key → ciphertext + shared_secret
3. Derive AES-256 key: SHA-256(shared_secret)
4. Encrypt plaintext: AES-256-GCM(key, nonce=12_random_bytes, plaintext)
5. Store: { ciphertext, encapsulated_key, nonce, key_id }
```

### Decryption Flow

```
1. Load Kyber private key by key_id from storage/keys/pqc_keys/{key_id}.json
2. Decapsulate: Kyber.decaps(private_key, encapsulated_key) → shared_secret
3. Derive AES-256 key: SHA-256(shared_secret)
4. Decrypt: AES-256-GCM(key, nonce, ciphertext) → plaintext
```

### Key Storage

- Location: `storage/keys/pqc_keys/{key_id}.json`
- Format: JSON with Base64-encoded `public_key` and `private_key` fields
- File permissions: `chmod 0o600` (owner read/write only)
- One unique keypair per document

**Fallback:** If `liboqs-python` is unavailable, the system uses simulated keys (demo only — not quantum-resistant).

---

## Digital Signatures

**File:** `src/digital_signature.py`

### Algorithm: CRYSTALS-Dilithium3 (ML-DSA-65, NIST FIPS 204)

Post-quantum digital signature scheme. Provides non-repudiation and integrity verification that remains secure against quantum computers.

### Signing Flow

```
1. Hash document content + classification metadata → SHA-256 digest
2. Sign digest with Dilithium3 private key
3. Store: storage/signatures/{doc_id}.json
```

### Verification Flow

```
1. Re-hash document content + metadata
2. Verify stored signature against re-hash using Dilithium3 public key
3. Return verified: true/false
```

### Signature File Format

```json
{
  "doc_id": "...",
  "content_hash": "<SHA-256 hex>",
  "signature_hash": "<Dilithium3 signature hex>",
  "key_id": "SIG_DILITHIUM3_DEFAULT",
  "algorithm": "CRYSTALS-Dilithium3 (ML-DSA-65)",
  "timestamp": "2026-04-23T15:35:00.000000",
  "verified": true
}
```

### Key Management

- Default keypair for all documents: `storage/keys/signature_keys/SIG_DILITHIUM3_DEFAULT.json`
- Per-document keypairs supported if required
- Base64-encoded keys stored as JSON
- File permissions: `chmod 0o600`

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/verify-signature/<doc_id>` | Verify document signature |
| `POST` | `/api/signature-comparison` | Compare signature approaches |
| `GET` | `/api/signature-status` | Overall signature system status |

---

## OCR: Qwen2.5-VL & Tesseract

**Files:** `src/qwen_ocr.py` · `src/pdf_extractor.py`

### Dual OCR Strategy

**Primary: Qwen2.5-VL-3B-Instruct (Vision-Language Model)**

- Local inference, no external API calls
- Supports Arabic + English natively
- High accuracy on ID cards, passports, handwritten content, and scanned documents
- Processing speed: ~30–80 seconds per page on CPU (no GPU required)
- Capped at 10 pages maximum (remaining pages fall back to Tesseract)
- Model location: `models/` directory (~7GB, two safetensors shards)
- Lazy-loaded on first use to minimize startup time
- Result flag: `ocr_engine: "qwen2.5-vl"` in pipeline output

**Fallback: Tesseract OCR**

- Fast: <1 second per page
- Supports Arabic (`eng+ara` language pack)
- Auto-detects installation path:
  - macOS (Apple Silicon): `/opt/homebrew/opt/tesseract/bin/tesseract`
  - Linux: `/usr/bin/tesseract`

### PDF Extraction Strategy (Priority Order)

1. **Direct text extraction (PyMuPDF)** — If the PDF has embedded selectable text, extract it directly without OCR
2. **Qwen2.5-VL OCR** — For scanned/image-based PDFs and image files
3. **Tesseract OCR** — Fallback if Qwen is unavailable or for remaining pages

### 6-Pass OCR Merge for High-Value ID Documents

For difficult documents (back of ID cards, national ID numbers), six OCR passes are merged:

| Pass | Configuration |
|------|--------------|
| 1 | Original — PSM 3 (auto) |
| 2 | Enhanced — PSM 6 (uniform block) |
| 3 | Binarized (threshold 140) — PSM 6 |
| 4 | Binarized (threshold 110) — PSM 4 (single column) |
| 5 | Sparse — PSM 11 (sparse text) |
| 6 | Digits-only whitelist pass |

All unique lines from all passes are **merged** (not the longest result picked) to ensure nothing is lost.

### Supported File Types

PDF, PNG, JPEG, GIF, BMP, TIFF, WebP

### OCR Prompts (Language-Aware)

- **Mixed Arabic + English:** `"Extract all Arabic and English text completely..."`
- **Arabic only:** `"أرجو استخراج النص العربي كاملاً..."`
- **English only:** `"Extract all English text..."`

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `QWEN_OCR_MODEL_DIR` | Override Qwen model directory path |
| `QWEN_MAX_PIXELS` | Override maximum pixel count for image processing |

### Async OCR Job Queue

Long-running OCR jobs are offloaded to a `ThreadPoolExecutor` background queue. The API returns a `job_id` immediately; the frontend polls `GET /api/ocr-job/{job_id}` for status and results.

---

## Blockchain Audit Trail

**Files:** `src/audit_trail.py` · `src/blockchain_protection.py`

### Block Structure

```python
Block:
  index          # Block number in chain
  timestamp      # ISO 8601 timestamp
  events         # List of audit events
  merkle_root    # SHA-256 root of event hashes
  previous_hash  # Hash of previous block (chain link)
  hash           # SHA-256 of block metadata
  nonce          # Proof-of-work nonce
  difficulty     # Work difficulty (default 2)
  block_signature  # Optional Dilithium3 signature of block hash
```

### Audit Event Types

| Event | Trigger |
|-------|---------|
| `DOCUMENT_CLASSIFIED` | Document processed through pipeline |
| `DOCUMENT_ENCRYPTED` | PQC encryption applied (C2/C3) |
| `ACCESS_GRANTED` | User successfully accessed a document |
| `ACCESS_DENIED` | User's access request was rejected |
| `DOCUMENT_VERIFIED` | Blockchain integrity check passed |
| `SIGNATURE_EVENT` | Digital signature created or verified |
| `FLAG_CREATED` | CISO flagged a document for review |
| `FLAG_RESOLVED` | CISO resolved a flag decision |

### Integrity Mechanisms

- **Merkle tree:** All events in a block hashed into a Merkle root — single event tampering changes the root
- **Hash chaining:** Each block stores the previous block's hash — any block modification breaks all subsequent hashes
- **Proof-of-work:** Mining loop increments nonce until block hash starts with `difficulty` leading zeros
- **Optional Dilithium3 block signatures:** Each block can be signed post-quantum for non-repudiation

### Storage Files

| File | Purpose |
|------|---------|
| `storage/audit_logs/blockchain.json` | Main audit blockchain |
| `storage/audit_logs/protection_chain.json` | Document content protection blockchain |
| `storage/audit_logs/audit_YYYY-MM-DD.jsonl` | Daily timestamped audit logs |
| `storage/audit_logs/pending_events.json` | Events awaiting mining (persists across restarts) |
| `storage/audit_logs/protection_pending.json` | Protection chain pending events |

**Important:** The blockchain file is loaded BEFORE genesis block creation. Genesis is only created if the chain is empty. This prevents the genesis block from overwriting an existing chain on restart.

---

## Confidence Scoring

**File:** `src/confidence_scoring.py`

Confidence is calculated from three independent factors:

### Factor 1: Agreement Score (weight 0.4)

Measures alignment between the LLM classification and the rules engine classification.

| Scenario | Score |
|----------|-------|
| Both agree on same level | 1.0 |
| One has stronger signal | 0.5–0.9 |
| Disagreement with hard triggers | 0.3 |

### Factor 2: Evidence Score (weight 0.4)

Measures strength of detected classification triggers.

| Trigger Type | Score |
|-------------|-------|
| Hard PII trigger (National ID, IBAN, credit card) | 1.0 |
| Soft keyword trigger | 0.5–0.8 |
| No triggers detected | 0.3 |

### Factor 3: LLM Score (weight 0.2)

LLM's own reported confidence from structured output.

| Scenario | Score |
|----------|-------|
| Structured JSON output | 0.9–1.0 |
| Fallback/unstructured output | 0.3–0.6 |

### Final Formula

```
Confidence = (Agreement × 0.4) + (Evidence × 0.4) + (LLM × 0.2)
```

The output also includes a natural-language explanation citing which factors contributed most and referencing the relevant PDPL/CBE legal basis.

---

## Role-Based Access Control (RBAC)

**File:** `src/rbac_system.py` (370 lines)

### User Levels & Roles

| Level | Role | Department | Summary |
|-------|------|-----------|---------|
| 1 | Viewer | None | C0 view only |
| 2 | Staff | Finance / Marketing / HR / Operations / Customer Service | C0, C1 |
| 3 | Analyst | Finance / Marketing / HR / Operations | C0, C1, C2 (view, no download) |
| 4 | Manager / DPO | Finance / Marketing / HR / Operations / All | C0–C3 (all actions except C3 download) |
| 5 | CISO | All departments | Full access to everything, no redaction |

### Access Matrix

| Level | C0 View | C0 Download | C1 View | C1 Download | C2 View | C2 Download | C3 View | C3 Download |
|-------|:-------:|:-----------:|:-------:|:-----------:|:-------:|:-----------:|:-------:|:-----------:|
| 1 | ✓ | ✓ | — | — | — | — | — | — |
| 2 | ✓ | ✓ | ✓ | ✓ | — | — | — | — |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### Field-Level Redaction

Fields masked based on access level for C2/C3 documents:

| Field | Level 1–2 | Level 3 | Level 4+ / CISO |
|-------|:---------:|:-------:|:---------------:|
| Name | ✓ | ✓ | ✓ |
| Email | ✓ | ✓ | ✓ |
| Phone | ✓ | ✓ | ✓ |
| Salary | — | ✓ | ✓ |
| Date of Birth | — | ✓ | ✓ |
| Address | — | ✓ | ✓ |
| National ID | — | — | ✓ |
| IBAN | — | — | ✓ |
| Account Number | — | — | ✓ |
| Passport | — | — | ✓ |
| Risk Rating | — | — | ✓ |
| Source of Funds | — | — | ✓ |
| Sanctions Result | — | — | ✓ |

### Department-Aware Access

- C2/C3 documents: user must be in the same department as the document's owning department **OR** be CISO/DPO (cross-department exception)
- C0/C1: department does not affect access (any authenticated user)

### Login Flow

1. User submits username/password to `POST /api/login`
2. Backend queries `config/users.json` and verifies credentials
3. Returns user object: `user_id`, `name`, `role`, `access_level`, `department`
4. Frontend stores in `localStorage['securedoc_user']`
5. All subsequent API calls include `user_id` for access control

---

## REST API Reference

**Base URL:** `http://127.0.0.1:5001/api`

### Authentication & Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/login` | Login with username/password |
| `GET` | `/logout` | Logout current session |
| `GET` | `/whoami` | Get current authenticated user |
| `GET` | `/users` | List all users |
| `GET` | `/user/<user_id>` | Get user details |

### Document Classification & Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/classify` | Classify raw text document |
| `POST` | `/upload` | Upload & classify PDF/image file (async OCR) |
| `GET` | `/ocr-job/<job_id>` | Poll async OCR job status and result |
| `POST` | `/redact` | Redact sensitive fields per access level |

### Document Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/documents` | List all stored documents |
| `GET` | `/document/<doc_id>` | Get document metadata & content |
| `GET` | `/document/<doc_id>/download` | Download original or encrypted file |
| `DELETE` | `/document/<doc_id>` | Delete stored document |
| `GET` | `/document/<doc_id>/verify` | Verify document integrity via blockchain |

### Access Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/access/<doc_id>` | Check user's access to document |
| `POST` | `/request-access` | Request access to restricted document |

### Blockchain & Integrity

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/protection-chain` | View document protection blockchain |
| `GET` | `/signature/<doc_id>` | Retrieve document digital signature |
| `GET` | `/verify-signature/<doc_id>` | Verify document signature |
| `POST` | `/signature-comparison` | Compare signature approaches |
| `GET` | `/signature-status` | Signature system overall status |

### Audit Trail

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/audit-logs` | Retrieve audit trail (blockchain events) |
| `GET` | `/audit-chain-status` | Verify audit chain integrity |
| `POST` | `/audit-export` | Export audit logs to CSV/JSON |

### Settings & Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/settings` | Get current pipeline settings |
| `POST` | `/settings` | Update classification settings |
| `GET` | `/settings/defaults` | Get default settings |

### Analytics & Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/statistics` | Pipeline stats (docs processed, encrypted count) |
| `GET` | `/classification-distribution` | C0/C1/C2/C3 count breakdown |

### Benchmarking

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/benchmark/ab-test` | Run A/B test (hybrid vs. LLM-only) |
| `GET` | `/benchmark/results` | Retrieve benchmark results |
| `POST` | `/benchmark/signature-test` | Run signature performance test |

### Admin / CISO Functions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ciso/override` | CISO override for access decisions |
| `POST` | `/ciso/flag` | Flag document for manual review |
| `GET` | `/ciso/flagged` | List all flagged documents |
| `POST` | `/ciso/resolve-flag` | Resolve a flag decision |

---

## Frontend Interface

**Technology:** React 18.3.1 · TypeScript 5 · Vite 6.3.5 · Tailwind CSS 4.1.12 · Recharts 2.15.2 · Radix UI

### Components

**LoginPage.tsx** — Username/password authentication form. Connects to `POST /api/login`. User object stored in `localStorage['securedoc_user']`.

**Dashboard.tsx** — Main landing view after login. Statistics cards (documents processed, C0/C1/C2/C3 counts, encrypted document count). Recharts pie chart for classification distribution. Bar chart timeline. Quick-links to Upload, History, and Audit Trail.

**UploadView.tsx** — Drag-and-drop PDF/image upload. Launches async OCR job and polls `/api/ocr-job/{job_id}` for real-time extraction progress. Displays classification results, confidence score, detected triggers, and CDE fields when complete.

**HistoryView.tsx** — Paginated table of all stored documents. Filter by classification level (C0/C1/C2/C3) or search by doc_id/filename. Shows timestamp, confidence, file type, and classification. Links to DocumentViewer for each document.

**DocumentViewer.tsx** — Full document detail. Shows classification metadata, confidence breakdown, detected triggers, Critical Data Elements, field-level redaction based on logged-in user's access level, and blockchain integrity status. Supports verifying document against protection chain.

**AuditTrailView.tsx** — Timeline of all blockchain audit events (CLASSIFIED, ENCRYPTED, ACCESS_GRANTED, ACCESS_DENIED, etc.). Verify full blockchain integrity. Filter by event type, user, or timestamp range. Level 5 (CISO) sees detailed reasoning; other levels see summarized events.

**SettingsView.tsx** — Pipeline configuration controls: confidence threshold slider (0–100%), hybrid mode selector (conservative / balanced / aggressive), auto-escalation toggle, auto-encrypt C2/C3 toggle, enable blockchain protection toggle, enable digital signatures toggle.

**PipelineStepsView.tsx** — Visual diagram of the 5-stage pipeline with per-stage timing, status badges (Completed / Failed / Skipped), and detailed stage output for the last processed document.

**VerificationView.tsx** — Dedicated view for signature and blockchain integrity checks. Shows verification status, key ID, algorithm, and timestamp for both digital signatures and protection chain.

**SecurityBadge.tsx** — Inline classification badge with color coding: C0 = green, C1 = yellow, C2 = orange, C3 = red.

**Navigation.tsx** — Top navigation bar with route links (Dashboard, Upload, History, Audit Trail, Settings), current user display, and logout button.

### UI Library

Radix UI primitives (30+ components): Card, Button, Dialog, Tab, Alert, Badge, Input, Slider, Toggle, Select, Checkbox, Table, Pagination, Breadcrumb, Tooltip, Popover, Dropdown Menu — all styled with Tailwind CSS.

---

## Configuration & Users

### config/users.json — Demo Users

All demo users use password: **`demo123`**

| Username | Name | Role | Level | Department |
|----------|------|------|-------|-----------|
| `ciso` | Noor Elhemaly | CISO | 5 | All |
| `dpo` | Data Protection Officer | DPO | 4 | All |
| `finance_manager` | Ahmed Samy Hassan | Finance Manager | 4 | Finance |
| `finance_analyst` | Mona Kamal Nasser | Analyst | 3 | Finance |
| `finance_staff` | Khaled Farouk Ibrahim | Staff | 2 | Finance |
| `marketing_manager` | Sara Tarek Mahmoud | Manager | 4 | Marketing |
| `marketing_analyst` | Omar Adel Youssef | Analyst | 3 | Marketing |
| `marketing_staff` | Nadia Hassan Ali | Staff | 2 | Marketing |
| `hr_manager` | Fatma Mostafa Selim | HR Manager | 4 | HR |
| `hr_analyst` | Mohamed Gamal Abdel | Analyst | 3 | HR |
| `hr_staff` | Amira Samir Lotfy | Staff | 2 | HR |
| `customer_service_officer` | Layla Mostafa Kamel | CSO | 2 | Customer Service |
| `branch_operations` | Tarek Hussein Shahin | Operations Officer | 3 | Operations |
| `branch_manager` | Walid Anwar Farid | Branch Manager | 4 | Operations |
| `viewer` | Guest Viewer | Viewer | 1 | None |

### Pipeline Settings (Configurable via UI or API)

| Setting | Default | Description |
|---------|---------|-------------|
| Confidence threshold | 70% | Minimum confidence before flagging for manual review |
| Hybrid mode | balanced | `conservative` / `balanced` / `aggressive` |
| Auto-escalate | true | Automatically upgrade classification on hard triggers |
| Auto-encrypt C2/C3 | true | Apply PQC encryption to C2 and C3 documents |
| Blockchain protection | true | Record content hash in protection chain |
| Digital signatures | true | Sign documents with Dilithium3 |

---

## Demo Documents & Dataset

**151 total demo PDFs** — all from an Egyptian banking context (Bank Misr, Edge Bank, ADIB, NBE, and others).

| Folder | Count | Classification | Document Types |
|--------|-------|----------------|---------------|
| `demo_documents/C0/` | 39 | Public | Press releases, annual reports, governance manuals, job postings, interest rate tables, product brochures, sustainability reports, CBE circulars |
| `demo_documents/C1/` | 36 | Internal | Training schedules, IT alerts, staff memos, operations bulletins, compliance statements, internal circulars, committee meeting minutes |
| `demo_documents/C2/` | 32 | Confidential | Job offer letters, vendor contracts, internal audit memos, market analysis, service agreements, strategic plans |
| `demo_documents/C3/` | 35 | Highly Sensitive | Payroll records, KYC forms, loan applications, credit assessments, account statements, SAR documents, salary certificates, identity verifications |
| `demo_documents/Account_Opening/` | 24 | Mixed C1–C3 | Account opening forms, KYC templates, customer identity verification |

Ground truth labels are provided in:
- `dataset_ground_truth.csv` — CSV format
- `dataset_ground_truth.json` — JSON format

---

## Storage Structure

```
storage/
├── secure_storage/
│   └── {doc_id}.json                  # C2/C3: encrypted ciphertext + key_id + nonce
│                                       # C0/C1: plaintext content + metadata
│
├── audit_logs/
│   ├── blockchain.json                # Main audit blockchain (array of blocks)
│   ├── protection_chain.json          # Document content integrity blockchain
│   ├── audit_YYYY-MM-DD.jsonl         # Daily timestamped audit event logs
│   ├── pending_events.json            # Events awaiting blockchain mining
│   └── protection_pending.json        # Protection chain pending events
│
├── keys/
│   ├── pqc_keys/
│   │   └── PQC_{timestamp}_{id}.json  # Kyber-768 keypair (Base64, chmod 0o600)
│   └── signature_keys/
│       └── SIG_DILITHIUM3_DEFAULT.json  # Dilithium3 keypair (Base64, chmod 0o600)
│
└── original_files/
    ├── {doc_id}.pdf                   # Original uploaded PDF files
    └── {doc_id}.png                   # Original uploaded image files
```

---

## Installation & Setup

### Prerequisites

| Component | Version | Required |
|-----------|---------|---------|
| Python | 3.8+ | Required |
| Node.js | 18+ | Required |
| Ollama | Latest | Required (LLM) |
| Tesseract OCR | 4+ | Required (OCR fallback) |
| liboqs-python | Latest | Required (PQC encryption) |
| GPU | Any CUDA GPU | Optional (speeds up Qwen OCR) |

### 1. Python Backend Dependencies

```bash
# Core framework
pip install flask flask-cors

# Document processing
pip install pymupdf pytesseract pillow pdf2image requests

# Post-quantum cryptography
pip install liboqs-python            # CRYSTALS-Kyber-768 (Kyber KEM)

# Digital signatures
pip install dilithium-py             # CRYSTALS-Dilithium3

# Standard cryptography (AES-GCM)
pip install cryptography

# OCR model (optional — required for Qwen2.5-VL)
pip install torch==2.10.0
pip install transformers==5.3.0
pip install accelerate==1.13.0
pip install torchvision==0.25.0

# Benchmarking (optional)
pip install psutil
```

### 2. Install Tesseract

```bash
# macOS (Homebrew)
brew install tesseract tesseract-lang      # Includes Arabic language pack

# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-ara

# Verify
tesseract --version
```

### 3. Install & Configure Ollama

```bash
# Install Ollama from https://ollama.ai/
# Then pull the LLaMA 3 model (~4GB)
ollama pull llama3

# Start Ollama server (keep running in background)
ollama serve                              # Listens on http://localhost:11434
```

### 4. Frontend Dependencies

```bash
cd "AI Document Classification Interface"
npm install
```

---

## Running the Application

### 1. Start Ollama (in a separate terminal)

```bash
ollama serve
```

### 2. Start the Flask API

```bash
# From the project root
python web_api.py
# Starts on http://127.0.0.1:5001
```

### 3. Start the React Frontend

```bash
cd "AI Document Classification Interface"
npm run dev
# Starts on http://127.0.0.1:5173
```

### 4. Open the Application

Navigate to **http://127.0.0.1:5173** in your browser.

**Quick Login:**
- Username: `ciso` (full access) or `finance_analyst` (scoped access)
- Password: `demo123`

### 5. Classify a Document

1. Go to the **Upload** tab
2. Drag & drop any PDF from `demo_documents/`
3. Wait for OCR extraction and classification (30–120 seconds depending on file complexity and whether Qwen is used)
4. View the classification result, confidence score, detected triggers, and encrypted status

### 6. Explore History & Audit

- **History tab** — all processed documents, filterable by classification level
- **Audit Trail tab** — blockchain event log with chain integrity verification

### 7. CLI Mode (Pipeline Only)

```bash
python src/main_pipeline.py
# Options:
#   1. Classify a single text document
#   2. Upload and classify a PDF/image file
#   3. Load from synthetic training dataset
#   4. Load from test dataset
#   5. Run A/B benchmark
```

---

## Benchmarking & Testing

### A/B Testing Framework (`src/benchmark.py`)

- Thread-safe concurrent document testing
- Measures classification accuracy against ground truth (`dataset_ground_truth.json`)
- Tracks per-stage timing for all 5 pipeline stages
- CPU and memory profiling (requires `psutil`)
- Exports results to CSV

```bash
# Via API
POST /api/benchmark/ab-test
GET  /api/benchmark/results
```

### Signature Performance (`src/signature_benchmark.py`)

- Measures Dilithium3 signing and verification latency
- Concurrent stress test (multiple simultaneous signatures)
- Comparison: baseline / blockchain-only / full signature
- Results documented in `docs/Digital_Signature_Comparison_Report.pdf`

```bash
# Via API
POST /api/benchmark/signature-test
```

### Ground Truth Dataset

- 151 documents with known labels in `dataset_ground_truth.csv` and `dataset_ground_truth.json`
- Use for measuring precision, recall, and F1 per classification level

---

## Known Issues & Fixes

### Template Detection False Positives

**Issue:** `is_likely_empty_template()` in `main_pipeline.py` incorrectly identifies filled-out C2/C3 documents as empty templates.

**Fix:** Check for filled C2-level data (account numbers, names, dates) before treating a document as an empty template.

### Blockchain Blocks Lost on Restart

**Issue:** `_create_genesis_block()` was called BEFORE `_load_blockchain()`, overwriting the saved `blockchain.json` on every restart.

**Fix:** Always call `_load_blockchain()` first; only call `_create_genesis_block()` if the loaded chain is empty.

### OCR Quality on ID Documents

**Issue:** Dual-pass OCR missed national ID numbers on the back of Egyptian ID cards.

**Fix:** 6-pass merged OCR (see [OCR section](#ocr-qwen25-vl--tesseract)). Key principle: MERGE all pass results, do not pick the longest. Each pass may capture different characters.

### User Info Missing in Audit Events

**Issue:** `user_id` / `user_name` fields were blank in classification audit events for anonymous uploads.

**Fix:** Always populate `user_id` and `user_name` in classification events, even for unauthenticated uploads (use `anonymous` as default).

### Port 5001 Conflicts

**Issue:** Flask fails to start because a previous instance is still running.

**Fix:** Kill stale Flask processes before restarting:
```bash
lsof -ti:5001 | xargs kill -9
```

---

## Regulatory Compliance

SecureDoc AI is designed to satisfy the following regulatory requirements:

| Regulation | Relevance |
|-----------|-----------|
| **Egypt PDPL No. 151/2020** | Art. 21: Special categories of personal data requiring enhanced protection → triggers C3 classification; non-repudiation via Dilithium3 |
| **CBE Information Security Framework** | Information classification framework (Public / Internal / Confidential / Strictly Confidential) → mapped to C0/C1/C2/C3 |
| **Banking Law No. 194/2020, Art. 97** | Confidentiality of customer banking information → C3 treatment for account/IBAN/transaction data |
| **NIST FIPS 204 (ML-DSA)** | CRYSTALS-Dilithium3 digital signatures → non-repudiation, quantum-resistant |
| **NIST FIPS 203 (ML-KEM)** | CRYSTALS-Kyber-768 key encapsulation → quantum-resistant encryption |
| **ISO 27001:2022** | Information security management — classification, access control, and audit trail align with Annex A controls |

---

*SecureDoc AI — Policy-Aware Hybrid AI Document Classification for Egyptian Banking*
*Coventry University — The Knowledge Hub · 2026*
