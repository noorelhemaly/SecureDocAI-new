#!/usr/bin/env python3
import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Any

# Import all components
from rbac_system import RBACSystem, User
from security_rules import SecurityRules
from audit_trail import AuditTrail, log_signature_event
from pqc_encryption import PQCEncryption
from confidence_scoring import calculate_confidence, ConfidenceScorer
from blockchain_protection import DocumentProtectionChain
from digital_signature import DocumentSignatureManager

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    # Base directory (parent of src/)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Config files
    USERS_FILE = os.path.join(BASE_DIR, "config", "users.json")
    AUDIT_LOG_FILE = os.path.join(BASE_DIR, "results", "audit_logs.json")
    ENCRYPTION_KEYS_FILE = os.path.join(BASE_DIR, "config", "pqc_encryption_keys.json")

    # Storage directories
    STORAGE_DIR = os.path.join(BASE_DIR, "storage", "secure_storage")
    AUDIT_LOGS_DIR = os.path.join(BASE_DIR, "storage", "audit_logs")
    PQC_KEYS_DIR = os.path.join(BASE_DIR, "storage", "keys", "pqc_keys")

    # Data directories
    DATA_DIR = os.path.join(BASE_DIR, "data")

    # Ensure directories exist
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.makedirs(AUDIT_LOGS_DIR, exist_ok=True)
    os.makedirs(PQC_KEYS_DIR, exist_ok=True)


# ============================================================================
# LLM CLASSIFIER (Using Ollama with LLaMA)
# ============================================================================

import requests
import re

class LLMClassifier:
    """LLaMA 3 classification using Ollama with keyword fallback"""

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        print(f"   🦙 LLM Classifier initialized: {model} via Ollama (with fallback)")

        self.system_prompt = """You are a document classification officer at Bank Misr, Egypt's largest state-owned bank.
        Your role is to classify every document for data protection, access control, 
        and regulatory compliance under Egypt's Personal Data Protection Law (PDPL) and 
        the Central Bank of Egypt (CBE) Information Security Framework.

Classify each document into exactly one level: C0, C1, C2, or C3.

══════════════════════════════════════════════════
CLASSIFICATION LEVELS
══════════════════════════════════════════════════

C0 — PUBLIC
Documents intended for general public distribution. No personal data whatsoever.
Examples:
  • Press releases, public regulatory announcements
  • Job postings on career websites or public boards
  • Product brochures, publicly published fee schedules
  • Interest rate tables published on the bank website
  • Customer-facing holiday notices, general service updates
  • Financial literacy or awareness materials for the public
  • Corporate governance manuals and codes of ethics published on the bank's website
  • Consumer protection frameworks and customer charters published publicly
  • CBE-published regulations, circulars, and supervisory frameworks (publicly issued)
  • Code of corporate governance for shareholders and public stakeholders
  • Publicly released annual reports and sustainability reports
  • Investor relations reports, quarterly earnings releases, financial highlights
  • Capital adequacy disclosures, Basel III Pillar 3 reports published publicly
  • Aggregate financial summaries (total assets, NPL ratio, ROE, NIM) for public audiences
Key test: Could this be posted on the bank's public website without any concern?
CRITICAL NOTE on C3 in public financial reports: Aggregate financial metrics (earnings per
share, return on equity, NPL ratio, capital adequacy ratio, risk-weighted assets, total
provisions) in a published investor relations or annual report are NOT C3 triggers —
they describe portfolio-level data, not a specific customer. C3 risk_rating means a
Low/Medium/High designation assigned to ONE SPECIFIC NAMED CUSTOMER, not a category of assets.

──────────────────────────────────────────────────

C1 — INTERNAL
Documents for bank employees only — no personal data.
If leaked, causes only operational embarrassment, not a privacy or contractual breach.
First names in a meeting context are acceptable ("Ahmed presented") — but
no contact details, IDs, or employment specifics.
Examples:
  • Internal policies, procedures, SOPs, circulars, guidelines
  • All-staff announcements (training schedules, IT alerts, system updates)
  • Business continuity plans, IT security guidelines
  • Meeting agendas and minutes (staff first names only, no contact info)
  • Internal department reports with no customer or personal data
  • Onboarding guides, training materials for employees
  • Quarterly training schedules (Q1/Q2/Q3/Q4) — even if they contain no sensitive data,
    a bank's staff training schedule is addressed to employees and is NOT a public document
  • Branch operations bulletins, IT maintenance notices, system downtime alerts
Key test: Is this for bank staff only, with no identifiable personal or business-confidential data?
IMPORTANT — do NOT call a training schedule, staff bulletin, or employee notice "C0 Public".
These are always C1 Internal even if the content seems routine or non-sensitive.

──────────────────────────────────────────────────

C2 — CONFIDENTIAL
Two independent paths — EITHER qualifies the document as C2.

  PATH A — PERSONAL DATA
  A real person's full name appears WITH at least one of:
    email address, phone number, home or work address, signature,
    employment terms, salary range (e.g. "EGP 15,000–20,000"),
    contractual terms naming the individual.
  Examples:
    • Job offer letters, employment contracts, termination letters
    • Performance reviews, performance improvement plans (PIPs)
    • Warning letters, disciplinary notices
    • Salary certificates (range only — exact figure is C3)
    • CVs and resumes with contact information
    • Customer correspondence containing name + email or phone
    • NDAs signed and named

  PATH B — BUSINESS CONFIDENTIAL
  The document involves a party outside the bank OR contains proprietary
  business information whose disclosure would harm the bank commercially or legally.
  Examples:
    • Vendor contracts, supplier agreements (IBM, Temenos, SWIFT, any vendor)
    • Service level agreements (SLAs), outsourcing agreements
    • Non-disclosure agreements with third parties
    • Pricing negotiations, commercial quotations, payment terms
    • Scope of work, statement of work, project deliverables
    • Marketing campaign briefs, agency contracts
    • Legal correspondence with external law firms or regulators
    • Internal audit reports and findings (even without PII)
    • Board presentations, executive strategy documents
    • M&A discussions, due diligence materials
    • Budget proposals, financial projections, ROI analyses
    • Competitive intelligence, market analysis
  Key test: Would sharing this with a competitor or the public harm the bank
    financially, legally, or reputationally? → C2

──────────────────────────────────────────────────

C3 — HIGHLY SENSITIVE
Documents containing regulated personal or financial data that create
direct regulatory liability under CBE rules or Egypt PDPL Art. 21.
ANY ONE of the triggers below classifies the ENTIRE document as C3:

  IDENTITY:
  • Egyptian National ID number (14 digits, starts with 2 or 3)
  • Passport number (one or two letters followed by digits)

  FINANCIAL IDENTIFIERS:
  • Egyptian IBAN (EG followed by 27 digits) — even partially masked (EG****)
  • Bank account number (a labeled "Account Number: XXXXXXXX" with 6-16 digits)
    CRITICAL: A bank account STATEMENT showing customer name + account number +
    balance + transactions is ALWAYS C3 — even if it has no National ID or IBAN.
    The account number itself is a C3 trigger. Do NOT classify account statements as C2.
  • Credit card number (16 digits in groups of 4)
  • EXACT salary in EGP — a specific figure such as "EGP 12,500/month",
    "net monthly salary is EGP 14,750", "exact net monthly salary is EGP 8,500"
    IMPORTANT: a salary RANGE (e.g. "EGP 10,000–15,000") is C2, not C3.
    A salary CERTIFICATE naming a specific employee with their exact salary → C3.
    Do NOT classify as C2 just because a National ID is absent — exact salary alone is C3.

  AML / KYC / COMPLIANCE:
  • Customer risk rating (a Low/Medium/High designation for a specific customer)
  • Sanctions screening result (World-Check, UN sanctions list, automated output)
  • Source of funds declaration
  • PEP (Politically Exposed Person) designation for a named individual

  Legal basis: Egypt PDPL Art. 21, CBE Framework §4.1,
               Banking Law No. 194/2020 Art. 97.

══════════════════════════════════════════════════
DECISION FLOWCHART — apply in order, stop at first match
══════════════════════════════════════════════════

1. Does the document contain any C3 trigger?
   (National ID • IBAN • account number • exact salary • passport •
    customer risk rating • sanctions result • source of funds • PEP)
   → YES → C3. Stop.

2. Does the document involve any party outside the bank?
   (vendor, supplier, partner, auditor, external law firm, regulator,
    customer who signed a contract, IBM, any named third-party company)
   → YES → C2 (Path B). Stop.
   IMPORTANT EXCEPTION: Publicly published regulations, governance codes, consumer
   protection frameworks, and supervisory circulars issued BY regulators (CBE, FRA)
   FOR the public are C0 — NOT C2. Path B applies only to PRIVATE correspondence
   or contracts WITH external parties, not to publicly issued regulatory documents.
   Ask: is this a published document FOR the public, or a private deal WITH an outsider?

3. Does the document contain proprietary business information?
   (pricing, strategy, budget, M&A, audit findings, competitive analysis)
   → YES → C2 (Path B). Stop.

4. Does the document contain a named individual with personal details?
   (full name + email, phone, address, salary range, employment/contract terms)
   → YES → C2 (Path A). Stop.

5. Is the document restricted to bank employees with no personal data?
   (policy, circular, internal memo, training, staff-only announcement)
   → YES → C1. Stop.
   NOTE: Governance manuals, codes of ethics, and corporate governance frameworks
   PUBLISHED on the bank's public website are C0, not C1 — even if they describe
   internal policies. The key test is: was this published FOR the general public
   or FOR employees only? Public publication → C0.

6. Is the document intended for public audiences?
   (press release, website content, public brochure, customer notice)
   → YES → C0.

DEFAULT: When uncertain between two adjacent levels → choose the HIGHER one.
Data protection always errs on the side of caution.

══════════════════════════════════════════════════
SPECIAL CASES
══════════════════════════════════════════════════

MASKED / REDACTED DATA (values replaced with XXXX, ****, ●●●●, [REDACTED]):
  Classify by what the document IS, not only what is visible.
  A loan application with a masked National ID → still C3.
  A contract with a redacted company name → still C2.
  Do not downgrade because data was masked.

EMPTY TEMPLATES (blank forms with no data filled in):
  Classify as C1. The template itself contains no sensitive data.
  Once filled with real data, the classification follows the content.

ARABIC DOCUMENTS — apply identical rules. Key Arabic terms:
  C3 signals: الرقم القومي (National ID) • ايبان / IBAN • رقم الحساب (account no.)
              راتب محدد (exact salary figure) • جواز سفر (passport)
  C2 signals: عقد (contract) • اتفاقية (agreement) • عرض عمل (job offer)
              السيرة الذاتية (CV) • مورد (vendor) • مقدم خدمة (service provider)
              ميزانية (budget) • استراتيجية (strategy)
  C1 signals: تعميم (circular) • موظفين (employees) • اجتماع (meeting)
              تدريب (training) • سياسة (policy) • داخلي (internal)

══════════════════════════════════════════════════
CONFIDENCE GUIDE
══════════════════════════════════════════════════
0.90–1.00  Clear C3 trigger found, or clearly public document — no ambiguity
0.75–0.89  Strong semantic match — document type and level both clear
0.60–0.74  Reasonable confidence — minor ambiguity in content or context
0.45–0.59  Uncertain — mixed signals or sparse text
Below 0.45 Very unclear — flag for human review

══════════════════════════════════════════════════
OUTPUT FORMAT — use exactly these labels, one per line
══════════════════════════════════════════════════
CLASSIFICATION: [C0/C1/C2/C3]
CONFIDENCE: [0.00 to 1.00]
PROCESS: [Account Opening / Loan Processing / Customer Service / Risk Assessment / Back Office — Finance / Back Office — HR / Back Office — Operations / Public Communications / Unknown]
STAGE: [Customer Identification / Risk Assessment / Account Setup / Ongoing Relationship / Credit Assessment / Internal Operations / Unknown]
DOCUMENT_TYPE: [specific document type, e.g. "Vendor Contract", "Employment Contract", "Payroll Report", "Internal Circular"]
CDE_DETECTED: [comma-separated critical data elements found, or NONE]
REASONING: [One concise paragraph: document type identified, decisive factor for the chosen level, which legal basis applies. Mask sensitive values: National ID → first 4 digits then ****, IBAN → EG****, account number → first 4 digits then ****]"""

        # Fallback keywords for when Ollama is not available
        self.fallback_keywords = {
            'C0': ['press release', 'job posting', 'public announcement', 'service update', 'holiday notice'],
            'C1': ['policy', 'procedure', 'standard operating', 'circular', 'bank-wide', 'all staff', 'all employees', 'guideline'],
            'C2': ['meeting minutes', 'minutes of', 'internal memo', 'contract', 'agreement', 'correspondence', 'campaign brief', 'job offer', 'vendor'],
            'C3': [
                # PII
                'national id', 'iban', 'passport number', 'credit card',
                # Financial
                'payroll', 'salary:', 'compensation package', 'stock options', 'account balance',
                'assets under management',
                # Strategic
                'merger', 'acquisition', 'board meeting', 'strategic plan', 'm&a',
                # Security & Legal
                'data breach', 'security incident', 'vulnerability', 'fraud investigation',
                'litigation', 'regulatory violation',
                # IP & Trade Secrets
                'proprietary', 'trade secret', 'algorithm', 'confidential formula',
                # Customer Data
                'customer database', 'customer list', 'client portfolio', 'competitive intelligence'
            ]
        }

    def classify(self, text: str) -> Dict[str, Any]:
        """Classify document using LLaMA via Ollama API with keyword fallback"""
        try:
            return self._classify_with_ollama(text)
        except Exception as e:
            print(f"   ⚠️ LLaMA/Ollama unavailable: {e}")
            print(f"   📋 Using keyword-based fallback classification...")
            return self._fallback_classify(text)

    def _fallback_classify(self, text: str) -> Dict[str, Any]:
        """Fallback keyword-based classification when Ollama is unavailable"""
        text_lower = text.lower()
        _empty = {'process': 'Unknown', 'stage': 'Unknown',
                  'document_type': 'General Banking Document', 'cde_detected': []}

        # Check for C3 indicators first (highest priority)
        for keyword in self.fallback_keywords['C3']:
            if keyword in text_lower:
                return {'classification': 'C3', 'confidence': None,
                        'reasoning': f'Fallback: Found sensitive keyword "{keyword}"',
                        **_empty}

        # Check C2
        for keyword in self.fallback_keywords['C2']:
            if keyword in text_lower:
                return {'classification': 'C2', 'confidence': None,
                        'reasoning': f'Fallback: Found confidential keyword "{keyword}"',
                        **_empty}

        # Check C1
        for keyword in self.fallback_keywords['C1']:
            if keyword in text_lower:
                return {'classification': 'C1', 'confidence': None,
                        'reasoning': f'Fallback: Found internal keyword "{keyword}"',
                        **_empty}

        # Check C0
        for keyword in self.fallback_keywords['C0']:
            if keyword in text_lower:
                return {'classification': 'C0', 'confidence': None,
                        'reasoning': f'Fallback: Found public keyword "{keyword}"',
                        **_empty}

        # Default to C1 (Internal) if no keywords match
        return {
            'classification': 'C1',
            'confidence': None,
            'reasoning': 'Fallback: No clear indicators, defaulting to Internal',
            'process': 'Unknown', 'stage': 'Unknown',
            'document_type': 'General Banking Document', 'cde_detected': []
        }

    def _classify_with_ollama(self, text: str) -> Dict[str, Any]:
        """Call Ollama API for classification — parses CLASSIFICATION/CONFIDENCE/REASONING format."""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"Classify this document:\n\n{text[:6000]}",
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 700
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            result_text = response.json().get("response", "")

            # --- Parse structured output: CLASSIFICATION / CONFIDENCE / PROCESS / STAGE /
            #     DOCUMENT_TYPE / CDE_DETECTED / REASONING ---
            cls_match   = re.search(r'CLASSIFICATION:\s*(C[0-3])', result_text, re.IGNORECASE)
            conf_match  = re.search(r'CONFIDENCE:\s*([0-9]+\.?[0-9]*)', result_text, re.IGNORECASE)
            proc_match  = re.search(r'PROCESS:\s*(.+?)(?=\n|\Z)', result_text, re.IGNORECASE)
            stage_match = re.search(r'STAGE:\s*(.+?)(?=\n|\Z)', result_text, re.IGNORECASE)
            dtype_match = re.search(r'DOCUMENT_TYPE:\s*(.+?)(?=\n|\Z)', result_text, re.IGNORECASE)
            cde_match   = re.search(r'CDE_DETECTED:\s*(.+?)(?=\n|\Z)', result_text, re.IGNORECASE)
            reasoning_match = re.search(
                r'REASONING:\s*(.+?)(?=\nCLASSIFICATION:|\Z)', result_text,
                re.IGNORECASE | re.DOTALL
            )

            if cls_match:
                classification = cls_match.group(1).upper()
                confidence = float(conf_match.group(1)) if conf_match else 0.75
                confidence = max(0.0, min(1.0, confidence))
                reasoning  = reasoning_match.group(1).strip() if reasoning_match else 'LLaMA classification'
                process    = proc_match.group(1).strip()  if proc_match  else 'Unknown'
                stage      = stage_match.group(1).strip() if stage_match else 'Unknown'
                doc_type   = dtype_match.group(1).strip() if dtype_match else 'General Banking Document'
                cde_raw    = cde_match.group(1).strip()   if cde_match   else 'none'
                cde_list   = [] if cde_raw.lower() in ('none', 'n/a', '') else \
                             [c.strip() for c in cde_raw.split(',') if c.strip()]
                return {
                    'classification': classification,
                    'confidence':     confidence,
                    'reasoning':      reasoning,
                    'process':        process,
                    'stage':          stage,
                    'document_type':  doc_type,
                    'cde_detected':   cde_list,
                    'source':         'llama'
                }

            # Fallback: try to find any C-level mention
            _fb = {'process': 'Unknown', 'stage': 'Unknown',
                   'document_type': 'General Banking Document', 'cde_detected': []}
            # Try to get at least a short excerpt from the raw response for the user
            _raw_excerpt = result_text.strip()[:300].replace('\n', ' ') if result_text else ''
            _fallback_reasoning = (
                f"LLaMA response did not follow structured format. "
                f"Raw excerpt: {_raw_excerpt}"
            ) if _raw_excerpt else 'Extracted from LLaMA response (parse failed)'
            for level in ['C3', 'C2', 'C1', 'C0']:
                if level in result_text:
                    return {'classification': level, 'confidence': None,
                            'reasoning': _fallback_reasoning,
                            'source': 'llama_fallback', **_fb}

            return {'classification': 'C1', 'confidence': None,
                    'reasoning': 'Could not parse LLaMA response, defaulting to C1',
                    'source': 'llama_error', **_fb}

        except requests.exceptions.ConnectionError:
            raise RuntimeError("Ollama not running. Start with: ollama serve")
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama request timed out")

    def _classify_fallback(self, text: str) -> Dict[str, Any]:
        """Fallback classification when Ollama is unavailable - no AI confidence available"""
        text_lower = text.lower()

        # Count keyword matches for each level
        matches = {}
        for level, keywords in self.fallback_keywords.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            matches[level] = count

        # Find best match
        best_level = max(matches, key=matches.get)
        best_count = matches[best_level]

        # No matches - default to C1
        if best_count == 0:
            return {
                'classification': 'C1',
                'confidence': None,  # No AI available
                'reasoning': 'No clear indicators found, defaulting to Internal',
                'source': 'fallback'
            }

        reasoning_map = {
            'C0': 'Public announcement or service information',
            'C1': 'Internal operational information',
            'C2': 'Confidential business/personal information',
            'C3': 'Highly sensitive data (salary/ID/IBAN)'
        }

        return {
            'classification': best_level,
            'confidence': None,  # No AI available - confidence only from AI
            'reasoning': f"{reasoning_map[best_level]} ({best_count} indicators found)",
            'source': 'fallback'
        }


# ============================================================================
# TEMPLATE/FORM DETECTION
# ============================================================================

def is_likely_empty_template(text: str) -> bool:
    """
    Detect if a document is likely an empty template/form without actual data.

    Empty templates should be classified as C1 (Internal), not C2 (Confidential),
    because they don't contain actual personal/confidential data.

    Returns:
        True if document appears to be an empty template
    """
    text_lower = text.lower()

    # 1. Check for template/form indicators
    template_indicators = [
        'please fill', 'please complete', 'enter your', 'fill in',
        'form', 'template', 'application form', 'agreement form',
        'to be completed', 'for bank use only', 'for office use',
        'account holder name', 'customer name', 'applicant name',
        'date:', 'signature:', 'branch:', 'account number:'
    ]
    template_score = sum(1 for indicator in template_indicators if indicator in text_lower)

    # 2. Check for placeholder patterns (empty fields)
    import re
    placeholder_patterns = [
        r'\.{3,}',           # ... (dotted lines)
        r'_{3,}',            # ___ (underlines)
        r'\[\s*\]',          # [ ] (empty brackets)
        r'/\s*/\s*/',        # / / / (date format)
        r':\s*$',            # Field labels ending with colon
    ]
    placeholder_count = sum(len(re.findall(p, text, re.MULTILINE)) for p in placeholder_patterns)

    # 3. Check for actual data (if present, NOT a template)
    # C3-level data patterns
    actual_data_patterns = [
        r'\b\d{14}\b',                    # 14-digit National ID
        r'\bEG\d{27}\b',                  # Egyptian IBAN
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card
        r'\b\d{1,3}[,،]\d{3}\s*(EGP|جنيه|USD|EUR)\b',   # Actual amounts
    ]
    has_actual_data = any(re.search(p, text, re.IGNORECASE) for p in actual_data_patterns)

    # C2-level data patterns (filled form fields = NOT an empty template)
    filled_form_indicators = [
        r'\b\d{6,10}\b',                  # Account/reference/RIM numbers (6-10 digits)
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # Filled dates (e.g., 9/2/2026)
    ]
    has_filled_fields = sum(1 for p in filled_form_indicators if re.search(p, text)) >= 1

    # Check if customer name fields are filled (name label followed by actual text, not placeholder)
    name_field_patterns = [
        r'(?:account holder name|customer name|applicant name)\s*[\n:]\s*[A-Za-z\u0600-\u06FF]{2,}',
    ]
    has_filled_name = any(re.search(p, text, re.IGNORECASE) for p in name_field_patterns)

    # If form has both a filled name AND filled fields, it's NOT an empty template
    if has_filled_name and has_filled_fields:
        has_actual_data = True

    # 4. Decision logic
    # If has actual data, NOT a template
    if has_actual_data:
        return False

    # If many template indicators OR placeholder patterns, likely a template
    if template_score >= 3 or placeholder_count >= 5:
        return True

    # If has some template indicators and no actual data
    if template_score >= 2 and placeholder_count >= 2:
        return True

    return False


# ============================================================================
# LLAMA-ONLY CLASSIFICATION (No Rules Override)
# ============================================================================

def llama_only_classify(text: str, llm_classifier: LLMClassifier) -> Dict[str, Any]:
    """
    Classify using LLaMA ONLY - no security rules interference
    """
    llm_result = llm_classifier.classify(text)

    return {
        'classification': llm_result['classification'],
        'confidence': llm_result['confidence'],
        'method': 'LLAMA_ONLY',
        'llm_classification': llm_result['classification'],
        'rules_classification': 'N/A',
        'reasoning': llm_result['reasoning'],
        'agreement': True,
        'triggers': []
    }


# ============================================================================
# HYBRID CLASSIFICATION (LLM + Security Rules) - Optional
# ============================================================================

def hybrid_classify(text: str, llm_classifier: LLMClassifier,
                   security_rules: SecurityRules,
                   confidence_threshold: float = 0.85,
                   hybrid_mode: str = 'conservative',
                   auto_escalate: bool = True) -> Dict[str, Any]:
    """
    Perform hybrid classification: LLM + Security Rules

    Args:
        text: Document text to classify
        llm_classifier: LLM classifier instance
        security_rules: Security rules instance
        confidence_threshold: Minimum confidence to trust LLM (0.0-1.0)
        hybrid_mode: 'conservative' (prefer higher security), 'balanced', 'aggressive' (prefer LLM)
        auto_escalate: Whether to escalate to higher classification on disagreement

    Strategy based on hybrid_mode:
    - conservative: Always use higher classification on disagreement
    - balanced: Use LLM if confident, else use higher
    - aggressive: Prefer LLM unless rules detect C3
    """

    # Step 1: LLM Classification
    llm_result = llm_classifier.classify(text)

    # Step 2: Security Rules Classification
    rules_result = security_rules.classify_by_rules(text)

    # Step 3: Hybrid Decision
    llm_class = llm_result['classification']
    rules_class = rules_result['classification']
    llm_confidence = llm_result['confidence']
    triggers = rules_result.get('triggers', []) if rules_class else []

    hierarchy = {'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3}

    # Hard triggers = pattern-matched evidence (regex-detected PII, not keyword guesses).
    # Only hard triggers can override the LLM — keyword-only signals defer to LLM semantics.
    HARD_TRIGGERS = {
        'National ID', 'Passport', 'IBAN', 'Salary', 'Account Number',
        'Credit Card', 'Personal Data', 'Masked Data', 'CV/Resume',
    }
    has_hard_trigger = any(t in HARD_TRIGGERS for t in triggers)

    # ── CASE 1: Rules found nothing → LLM decides ──────────────────────────────
    if rules_class is None:
        final_class = llm_class
        reasoning = llm_result.get('reasoning', 'AI classified, no rule triggers')
        if llm_class == 'C2' and is_likely_empty_template(text):
            final_class = 'C1'
            reasoning = f"Empty template — downgraded from C2 to C1. {reasoning}"
        # If LLM over-escalates to C3 but document only has a salary range → cap at C2
        elif llm_class == 'C3' and security_rules.detect_salary_range(text):
            final_class = 'C2'
            reasoning = (
                "Document contains a salary range/band (not an exact personal salary figure). "
                "Job offers and promotion letters with a salary range are C2 — individual "
                "employment records, not systemic risk data."
            )
        return {
            'classification': final_class,
            'confidence': llm_confidence,
            'method': 'AI_DECISION',
            'llm_classification': llm_class,
            'rules_classification': None,
            'reasoning': reasoning,
            'agreement': True,
            'triggers': [],
        }

    # ── CASE 2: Rules detected C3 (hard PII/financial triggers) ────────────────
    # All C3 triggers are now HIGH_PRECISION — LLM result is ignored when any
    # of these fire. Passport is included under PDPL Article 21: a passport number
    # uniquely identifies a specific individual and carries the same legal weight
    # as a National ID. There is no Case 2b / low-precision exception any more.
    if rules_class == 'C3':
        # All C3 triggers are unconditional — LLM is ignored:
        # National ID | Passport | IBAN | Credit Card | Salary | Account Number
        # (PDPL Art. 21 — each uniquely identifies or financially exposes an individual)
        agreement = (llm_class == 'C3')
        reasoning = f"Security rules detected: {', '.join(triggers)}"
        if agreement:
            reasoning = f"{llm_result['reasoning']} | Rules confirmed: {', '.join(triggers)}"
        return {
            'classification': 'C3',
            'confidence': llm_confidence,
            'method': 'AGREEMENT' if agreement else 'RULES_OVERRIDE',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': reasoning,
            'agreement': agreement,
            'triggers': triggers,
        }

    # ── CASE 3: Both classifiers agree ─────────────────────────────────────────
    if llm_class == rules_class:
        if triggers:
            reasoning = f"{llm_result['reasoning']} (Rules confirmed: {', '.join(triggers)})"
        else:
            reasoning = llm_result['reasoning']
        return {
            'classification': llm_class,
            'confidence': llm_confidence,
            'method': 'AGREEMENT',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': reasoning,
            'agreement': True,
            'triggers': triggers,
        }

    # ── CASE 4: Rules found hard PII evidence and want higher class than LLM ───
    # Rules detected actual personal data the LLM may have missed → escalate.
    if has_hard_trigger and hierarchy[rules_class] > hierarchy[llm_class]:
        return {
            'classification': rules_class,
            'confidence': llm_confidence,
            'method': 'RULES_ESCALATED',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': f"Rules escalated: {rules_result['reasoning']}",
            'agreement': False,
            'triggers': triggers,
        }

    # ── CASE 5: LLM says C3 but rules didn't confirm it ────────────────────────
    # If document has masked/redacted data, trust LLM's intent but cap at C2.
    # If rules confirmed this is a PUBLIC document (C0), do not trust LLM C3 —
    # aggregate risk language and financial figures in published reports are NOT C3.
    # Otherwise trust the LLM's semantic judgment for C3.
    if llm_class == 'C3' and rules_class != 'C3':
        # Rules confirmed publicly distributed document → trust rules → C0.
        # Annual reports, investor relations, consumer protection publications,
        # and press releases contain aggregate financial figures and risk language
        # that the LLM misreads as customer-specific C3 data. Check this FIRST
        # (before masked-data) so table asterisks in annual reports don't trigger C2.
        if rules_class == 'C0':
            return {
                'classification': 'C0',
                'confidence': llm_confidence,
                'method': 'RULES_OVERRIDE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': (
                    f"{llm_result['reasoning']} "
                    f"(Rules confirmed public document — LLM C3 overridden to C0; "
                    f"aggregate financial/risk data in public reports is not a C3 trigger)"
                ),
                'agreement': False,
                'triggers': triggers,
            }
        if security_rules.detect_masked_data(text):
            return {
                'classification': 'C2',
                'confidence': llm_confidence,
                'method': 'MASKED_DATA_DOWNGRADE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': 'Document contains masked/redacted PII — capped at C2 since raw values are not visible.',
                'agreement': False,
                'triggers': triggers + ['Masked Data'],
            }
        # Rules detected offer/promotion letter with salary → C2 (individual record).
        if 'Salary (Offer/Promotion Letter)' in triggers:
            return {
                'classification': 'C2',
                'confidence': llm_confidence,
                'method': 'RULES_OVERRIDE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': (
                    f"Individual employment offer or promotion letter — C2. "
                    f"One-to-one record; systemic risk requires bulk exposure."
                ),
                'agreement': False,
                'triggers': triggers,
            }
        # Rules detected a salary RANGE → cap at C2 (job offers and promotion
        # letters are individual records, not systemic risk — C2 is correct).
        if 'Salary Range' in triggers:
            return {
                'classification': 'C2',
                'confidence': llm_confidence,
                'method': 'RULES_OVERRIDE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': (
                    f"Document contains a salary range/band. Job offers and promotion letters "
                    f"are C2 — individual employment records, not systemic risk data."
                ),
                'agreement': False,
                'triggers': triggers,
            }
        # LLM sees semantic C3 indicators the rules didn't pattern-match
        return {
            'classification': 'C3',
            'confidence': llm_confidence,
            'method': 'AI_DECISION',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': llm_result['reasoning'],
            'agreement': False,
            'triggers': triggers,
        }

    # ── CASE 6: Rules say C1, LLM says C0 → trust rules only on strong signals ─
    # Generic internal keywords ('internal', 'training', 'team') appear in public
    # compliance statements and regulatory disclosures — not enough on their own.
    # Only escalate to C1 when the document contains an unambiguous structural
    # signal that it is addressed to internal staff and not for public distribution.
    STRONG_INTERNAL_SIGNALS = {
        # Explicit addressee markers — unambiguously internal
        'staff only', 'for internal use', 'for branch staff', 'branch staff',
        'internal circulation', 'not for distribution',
        'staff notice', 'staff memo', 'staff circular',
        # Document types that are inherently internal
        # NOTE: bare 'circular' and 'bulletin' are EXCLUDED — annual reports and
        # public regulatory documents routinely say "CBE circular No. X" or
        # "financial bulletin", which would falsely escalate a public C0 document.
        # Bare 'minutes' excluded: annual reports contain "board meeting minutes".
        # Bare 'memo' excluded: annual reports contain "internal memo" references.
        'memorandum',           # Full word — rarer in public docs than bare 'memo'
        'internal memo',        # Requires 'internal' qualifier
        'internal circular',    # Requires 'internal' qualifier
        'board minutes',        # Specific phrase — not the bare word 'minutes'
        'staff meeting',
        # Training schedules — always internal (staff calendars, course rosters)
        'training schedule', 'training plan', 'training calendar',
        'q1 training', 'q2 training', 'q3 training', 'q4 training',
        'staff training', 'training programme', 'training program',
        # Arabic equivalents
        'مذكرة داخلية', 'للاستخدام الداخلي', 'نشرة الفروع', 'تعميم داخلي',
        'جدول تدريب', 'خطة تدريب', 'برنامج التدريب',
    }
    if rules_class == 'C1' and llm_class == 'C0':
        text_lower_check = text.lower()
        # Governance/institutional documents (annual reports, investor relations,
        # regulatory frameworks) are public by definition — even if they happen to
        # contain a word like "circular" or "bulletin" in passing references to
        # CBE circulars. Trust the LLM's C0 decision for these.
        is_governance = any(sig in text_lower_check for sig in security_rules.governance_signals)
        if is_governance:
            return {
                'classification': 'C0',
                'confidence': llm_confidence,
                'method': 'AI_DECISION',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': (
                    f"{llm_result['reasoning']} "
                    f"(Governance/public document detected — rules C1 internal keywords "
                    f"overridden; annual reports and regulatory publications are C0)"
                ),
                'agreement': False,
                'triggers': triggers,
            }
        has_strong_internal = any(sig in text_lower_check for sig in STRONG_INTERNAL_SIGNALS)
        if has_strong_internal:
            return {
                'classification': 'C1',
                'confidence': llm_confidence,
                'method': 'RULES_ESCALATED',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': f"Rules escalated: {rules_result['reasoning']}",
                'agreement': False,
                'triggers': triggers,
            }

    # ── CASE 6.5: Rules say C0, LLM says C1 ────────────────────────────────────
    # Rules identified a governance/public document signal. If LLM's C1 came from
    # a parse failure or unstructured response (not a confident structured answer),
    # trust the pattern-based rules. If LLM explicitly returned a structured C1,
    # trust LLM (C1 is more conservative than C0 and may be correct for internal
    # governance publications not intended for the general public).
    if rules_class == 'C0' and llm_class == 'C1':
        llm_source = llm_result.get('source', '')
        if llm_source in ('llama_error', 'llama_fallback'):
            return {
                'classification': 'C0',
                'confidence': llm_confidence,
                'method': 'RULES_OVERRIDE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': (
                    f"LLM response not in structured format — rules identified a public "
                    f"document. Rules: {rules_result['reasoning']}"
                ),
                'agreement': False,
                'triggers': triggers,
            }

    # ── CASE 7: All other disagreements → trust LLM ────────────────────────────
    # Rules used only soft keyword signals. LLM's semantic understanding wins.
    return {
        'classification': llm_class,
        'confidence': llm_confidence,
        'method': 'AI_DECISION',
        'llm_classification': llm_class,
        'rules_classification': rules_class,
        'reasoning': llm_result['reasoning'],
        'agreement': False,
        'triggers': triggers,
    }


# ============================================================================
# DOCUMENT PROCESSING PIPELINE
# ============================================================================

class DocumentPipeline:
    """Complete document processing pipeline"""
    
    def __init__(self):
        """Initialize all components"""
        print("🚀 Initializing Document Processing Pipeline...\n")
        
        # Initialize components
        self.rbac = RBACSystem()
        self.security_rules = SecurityRules()
        self.audit = AuditTrail()
        self.pqc = PQCEncryption()
        self.llm = LLMClassifier()
        
        # Load users
        self._load_users()
        
        # Document counter
        self.doc_counter = 0
        
        print("✅ All components initialized successfully!\n")

    def _load_users(self):
        """Load users from JSON file"""
        try:
            with open(Config.USERS_FILE, 'r') as f:
                users_data = json.load(f)
                for _uid, user_data in users_data.items():
                    self.rbac.add_user(
                        user_id=user_data['user_id'],
                        name=user_data['name'],
                        access_level=user_data['access_level'],
                        role=user_data['role'],
                        department=user_data.get('department'),
                        username=user_data.get('username', user_data['user_id']),
                        password=user_data.get('password', ''),
                    )
            print(f"✅ Loaded {len(users_data)} users from {Config.USERS_FILE}")
        except FileNotFoundError:
            print(f"⚠️  {Config.USERS_FILE} not found, using default users")

    def process_document(self, doc_id: str, text: str, user_id: str = None,
                         confidence_threshold: float = 0.85,
                         hybrid_mode: str = 'conservative',
                         auto_escalate: bool = True,
                         auto_encrypt: bool = True,
                         store: bool = True,
                         true_label: str = None,
                         enable_blockchain_protection: bool = False,
                         enable_digital_signature: bool = False,
                         timing_mode: bool = False,
                         doc_department: str = None,
                         original_filename: str = None) -> Dict[str, Any]:
        """
        Process a single document through the complete pipeline

        Steps:
        1. Document ingestion
        2. Hybrid classification (LLM + Rules)
        3. PQC encryption (if C2/C3)
        4. Storage
        5. Audit logging
        6. Access control (if user_id provided)

        Args:
            doc_id: Unique document identifier
            text: Document content
            user_id: Optional user requesting access
            confidence_threshold: Minimum confidence for classification (0.0-1.0)
            hybrid_mode: 'conservative' (prefer higher security), 'balanced', or 'aggressive' (prefer LLM)
            auto_escalate: Whether to escalate when LLM and Rules disagree
            auto_encrypt: Whether to encrypt C2/C3 documents
            store: Whether to store the document (False for evaluation mode)
            true_label: Optional ground truth label for evaluation (C0, C1, C2, C3)
            enable_blockchain_protection: Whether to hash and protect document in blockchain
            enable_digital_signature: Whether to sign document with RSA-PSS digital signature
            timing_mode: Whether to record per-stage timing data

        Returns:
            Dictionary with processing results
        """
        self.doc_counter += 1
        
        print("=" * 80)
        print(f"📄 PROCESSING DOCUMENT {self.doc_counter}: {doc_id}")
        print("=" * 80)
        
        result = {
            'doc_id': doc_id,
            'timestamp': datetime.now().isoformat(),
            'stages': {}
        }

        stage_timings = {}

        # ========================================
        # STAGE 1: HYBRID AI CLASSIFICATION
        # ========================================
        _t_stage = time.perf_counter() if timing_mode else None
        print("\n🤖 STAGE 1: HYBRID AI CLASSIFICATION (LLaMA + Rules)")
        print(f"   Settings: mode={hybrid_mode}, threshold={confidence_threshold:.0%}, escalate={auto_escalate}")
        print("-" * 80)

        classification_result = hybrid_classify(
            text, self.llm, self.security_rules,
            confidence_threshold=confidence_threshold,
            hybrid_mode=hybrid_mode,
            auto_escalate=auto_escalate
        )

        # Calculate multi-factor confidence (academically grounded)
        # References: Dietterich (2000), Dempster-Shafer (1967), Salton & Buckley (1988), Vapnik (1995)
        confidence_result = calculate_confidence(
            classification=classification_result['classification'],
            llm_class=classification_result['llm_classification'],
            llm_raw_confidence=classification_result['confidence'],
            rules_class=classification_result['rules_classification'],
            triggers=classification_result.get('triggers', []),
            method=classification_result['method']
        )

        # Update classification result with scientific confidence
        classification_result['confidence'] = confidence_result['confidence']
        classification_result['confidence_factors'] = confidence_result['factors']
        classification_result['confidence_explanation'] = confidence_result['explanation']
        classification_result['confidence_formula'] = confidence_result['formula']
        classification_result['llm_raw_confidence'] = confidence_result['llm_raw_confidence']

        print(f"   🦙 LLaMA Classification: {classification_result['llm_classification']}")
        print(f"   📋 Rules Classification: {classification_result['rules_classification']}")
        print(f"   Method:                  {classification_result['method']}")
        print(f"   Agreement:               {'✓ Yes' if classification_result['agreement'] else '✗ No'}")
        print(f"   Final Classification:    🎯 {classification_result['classification']}")
        print(f"   Confidence:              {classification_result['confidence']:.0%} (Multi-factor)")
        print(f"   Factors:                 Agreement={confidence_result['factors']['agreement']:.2f}, Evidence={confidence_result['factors']['evidence']:.2f}")
        
        if classification_result['triggers']:
            print(f"   Triggers Detected:     {', '.join(classification_result['triggers'])}")
        
        result['stages']['classification'] = classification_result
        
        # Log classification with user info
        classification_event_data = {
            'document_id': doc_id,
            'classification': classification_result['classification'],
            'method': classification_result['method'],
            'triggers': classification_result['triggers']
        }
        # Always include user info in audit event
        if user_id:
            user = self.rbac.get_user(user_id)
            classification_event_data['user_id'] = user_id
            if user:
                classification_event_data['user_name'] = user.name
                classification_event_data['user_level'] = user.access_level
            else:
                classification_event_data['user_name'] = user_id
        else:
            classification_event_data['user_id'] = 'anonymous'
            classification_event_data['user_name'] = 'Anonymous Upload'

        self.audit.log_event(
            event_type="DOCUMENT_CLASSIFIED",
            data=classification_event_data
        )

        if timing_mode and _t_stage is not None:
            stage_timings['classification_ms'] = round((time.perf_counter() - _t_stage) * 1000, 2)

        # ========================================
        # STAGE 2: PQC ENCRYPTION (C2/C3 only)
        # ========================================
        _t_stage = time.perf_counter() if timing_mode else None
        print("\n🔐 STAGE 2: POST-QUANTUM ENCRYPTION")
        print(f"   Auto-encrypt C2/C3: {auto_encrypt}")
        print("-" * 80)

        classification = classification_result['classification']

        if classification in ['C2', 'C3'] and auto_encrypt:
            # Encrypt the document
            encrypted_data = self.pqc.encrypt(text, classification)
            
            print(f"   Status:                ✅ ENCRYPTED")
            print(f"   Algorithm:             Kyber-768 + AES-256-GCM")
            print(f"   Original Size:         {len(text)} characters")
            print(f"   Ciphertext Size:       {len(encrypted_data['ciphertext'])} hex chars")
            print(f"   Quantum Resistant:     ✅ YES (NIST 2024 approved)")
            
            # Store encrypted version
            result['stages']['encryption'] = {
                'encrypted': True,
                'algorithm': 'Kyber-768 + AES-256-GCM',
                'ciphertext': encrypted_data['ciphertext'],
                'key_id': encrypted_data['key_id'],
                'encapsulated_key': encrypted_data['encapsulated_key'],
                'nonce': encrypted_data['nonce'],
                'shared_secret': encrypted_data.get('shared_secret')  # For demo fallback
            }
            
            # Log encryption with user info
            encryption_event_data = {
                'document_id': doc_id,
                'classification': classification,
                'algorithm': 'PQC',
                'key_id': encrypted_data['key_id']
            }
            if user_id:
                user = self.rbac.get_user(user_id)
                encryption_event_data['user_id'] = user_id
                if user:
                    encryption_event_data['user_name'] = user.name
                    encryption_event_data['user_level'] = user.access_level

            self.audit.log_event(
                event_type="DOCUMENT_ENCRYPTED",
                data=encryption_event_data
            )
        else:
            print(f"   Status:                ⚪ NOT ENCRYPTED")
            print(f"   Reason:                C0/C1 documents stored as plaintext")
            
            result['stages']['encryption'] = {
                'encrypted': False,
                'reason': 'C0/C1 documents do not require encryption'
            }

        if timing_mode and _t_stage is not None:
            stage_timings['encryption_ms'] = round((time.perf_counter() - _t_stage) * 1000, 2)

        # ========================================
        # STAGE 3: SECURE STORAGE
        # ========================================
        _t_stage = time.perf_counter() if timing_mode else None
        print("\n💾 STAGE 3: SECURE STORAGE")
        print("-" * 80)

        if store:
            storage_path = os.path.join(Config.STORAGE_DIR, f"{doc_id}.json")

            metadata = {
                'text_length': len(text),
                'classification_method': classification_result['method'],
                'triggers': classification_result['triggers'],
                'reasoning': classification_result.get('reasoning', ''),
                'confidence': classification_result.get('confidence'),
                'confidence_factors': classification_result.get('confidence_factors', {}),
                'confidence_explanation': classification_result.get('confidence_explanation', ''),
                'llm_classification': classification_result.get('llm_classification'),
                'rules_classification': classification_result.get('rules_classification'),
                'agreement': classification_result.get('agreement'),
                'llm_raw_confidence': classification_result.get('llm_raw_confidence'),
            }

            # Store ground truth label if provided (for evaluation)
            if true_label:
                metadata['true_label'] = true_label
                metadata['correct'] = classification == true_label

            # ── Human-in-the-Loop: determine verification routing ──────────
            ai_confidence = classification_result.get('confidence') or 0.0
            ai_classification = classification_result.get('llm_classification') or classification
            agreement = classification_result.get('agreement', True)
            ai_reasoning = classification_result.get('reasoning', '')

            # New structured fields from LLM
            doc_process   = classification_result.get('process', 'Unknown')
            doc_stage     = classification_result.get('stage', 'Unknown')
            doc_type      = classification_result.get('document_type', 'General Banking Document')
            cde_detected  = classification_result.get('cde_detected', [])

            # Enrich with security rules check_c3_triggers for completeness
            cde_from_rules = []
            try:
                cde_map = self.security_rules.check_c3_triggers(text)
                cde_from_rules = [k for k, v in cde_map.items() if v]
                # Merge LLM CDEs with rules CDEs (rules are authoritative for PII)
                merged_cde = list(set(cde_detected) | set(cde_from_rules))
                cde_detected = merged_cde
            except Exception:
                pass

            # Write back merged CDEs so the API response contains them
            classification_result['cde_detected'] = cde_detected
            result['stages']['classification']['cde_detected'] = cde_detected

            # Enrich document_type from rules if LLM gave generic result
            if doc_type in ('General Banking Document', 'Unknown', '') and text:
                try:
                    type_result = self.security_rules.identify_document_type(text)
                    if type_result.get('confidence', 0) >= 0.80:
                        doc_process = doc_process if doc_process != 'Unknown' else type_result['process']
                        doc_stage   = doc_stage   if doc_stage   != 'Unknown' else type_result['stage']
                        doc_type    = type_result['document_type']
                except Exception:
                    pass

            # Did the security rules engine (not just AI) detect C3 triggers?
            rules_detected_c3 = (classification_result.get('rules_classification') == 'C3')
            # Did the AI say C3?
            ai_said_c3 = (ai_classification == 'C3')

            # All documents are immediately active — no verification queue
            doc_status = 'ACTIVE'

            # Uploader department: from user or explicit param
            uploader_dept = doc_department
            if not uploader_dept and user_id:
                uploader = self.rbac.get_user(user_id)
                if uploader:
                    uploader_dept = uploader.department

            storage_data = {
                'doc_id': doc_id,
                'classification': classification,
                'timestamp': result['timestamp'],
                'original_text': text if classification in ['C0', 'C1'] else None,
                'encrypted_data': result['stages']['encryption'] if result['stages']['encryption']['encrypted'] else None,
                'metadata': metadata,
                'status': doc_status,
                'ai_classification': ai_classification,
                'ai_confidence': ai_confidence,
                'ai_reasoning': ai_reasoning,
                'final_classification': classification,
                'original_ai_classification': ai_classification,
                'ai_rules_agreed': agreement,
                'rules_detected_c3': rules_detected_c3,
                'ai_said_c3': ai_said_c3,
                # Department / uploader
                'department': uploader_dept,
                'original_filename': original_filename,
                'uploaded_by': user_id,
                # Structured classification metadata
                'process': doc_process,
                'stage': doc_stage,
                'document_type': doc_type,
                'cde_detected': cde_detected,
            }

            with open(storage_path, 'w', encoding='utf-8') as f:
                json.dump(storage_data, f, indent=2, ensure_ascii=False)

            # Always update the protection chain after writing the file,
            # regardless of the enableBlockchainProtection setting.
            # Verification runs unconditionally in get_stored_documents,
            # so the chain must always reflect the current file state to
            # avoid false TAMPERED badges on re-uploads.
            try:
                _pc = DocumentProtectionChain(storage_dir=Config.STORAGE_DIR)
                _enc_stage = result.get('stages', {}).get('encryption', {})
                _pc_content = (
                    _enc_stage.get('ciphertext', text)
                    if _enc_stage.get('encrypted')
                    else text
                )
                _pc.protect_document(
                    doc_id=doc_id,
                    content=_pc_content,
                    classification=classification,
                    metadata={
                        'classification_method': classification_result['method'],
                        'triggers': classification_result.get('triggers', []),
                        'confidence': classification_result.get('confidence'),
                    },
                    user_id=user_id,
                )
            except Exception:
                pass

            print(f"   Storage Path:          {storage_path}")
            print(f"   Classification:        {classification}")
            print(f"   Encrypted:             {'✅ YES' if result['stages']['encryption']['encrypted'] else '⚪ NO'}")
            print(f"   Status:                ✅ STORED SUCCESSFULLY")

            result['stages']['storage'] = {
                'path': storage_path,
                'stored': True
            }
        else:
            print(f"   Status:                ⚪ SKIPPED (evaluation mode)")
            result['stages']['storage'] = {
                'path': None,
                'stored': False
            }

        if timing_mode and _t_stage is not None:
            stage_timings['storage_ms'] = round((time.perf_counter() - _t_stage) * 1000, 2)

        # ========================================
        # STAGE 3.5: BLOCKCHAIN DOCUMENT PROTECTION
        # ========================================
        if enable_blockchain_protection:
            _t_stage = time.perf_counter() if timing_mode else None
            print("\n🔗 STAGE 3.5: BLOCKCHAIN DOCUMENT PROTECTION")
            print("-" * 80)

            protection_chain = DocumentProtectionChain(
                storage_dir=Config.STORAGE_DIR,
            )
            # For encrypted docs, hash the ciphertext (original text is wiped from storage).
            # For plain docs, hash the original text as usual.
            _enc_stage = result.get('stages', {}).get('encryption', {})
            _protection_content = (
                _enc_stage.get('ciphertext', text)
                if _enc_stage.get('encrypted')
                else text
            )
            protection_result = protection_chain.protect_document(
                doc_id=doc_id,
                content=_protection_content,
                classification=classification,
                metadata={
                    'classification_method': classification_result['method'],
                    'triggers': classification_result.get('triggers', []),
                    'confidence': classification_result.get('confidence'),
                },
                user_id=user_id,
            )

            print(f"   Content Hash:          {protection_result['content_hash'][:32]}...")
            print(f"   Protection Time:       {protection_result['elapsed_ms']:.2f} ms")
            print(f"   Status:                ✅ PROTECTED")

            result['stages']['blockchain_protection'] = protection_result

            if timing_mode and _t_stage is not None:
                stage_timings['blockchain_protection_ms'] = round(
                    (time.perf_counter() - _t_stage) * 1000, 2
                )

        # ========================================
        # STAGE 3.5b: DIGITAL SIGNATURE PROTECTION
        # ========================================
        if enable_digital_signature:
            _t_stage = time.perf_counter() if timing_mode else None
            print("\n🖊️  STAGE 3.5b: DIGITAL SIGNATURE PROTECTION")
            print("-" * 80)

            sig_manager = DocumentSignatureManager()
            sig_result = sig_manager.sign_document(
                doc_id=doc_id,
                content=text,
                classification=classification,
                metadata={
                    'classification_method': classification_result['method'],
                    'triggers': classification_result.get('triggers', []),
                    'confidence': classification_result.get('confidence'),
                },
                user_id=user_id,
            )

            print(f"   Content Hash:          {sig_result['content_hash'][:32]}...")
            print(f"   Signature Hash:        {sig_result['signature_hash'][:32]}...")
            print(f"   Algorithm:             {sig_result['algorithm']}")
            print(f"   Signature Time:        {sig_result['elapsed_ms']:.2f} ms")
            print(f"   Status:                ✅ SIGNED")

            # Embed signature hash in the blockchain audit trail
            log_signature_event(
                self.audit,
                document_id=doc_id,
                content_hash=sig_result['content_hash'],
                signature_hash=sig_result['signature_hash'],
                key_id=sig_result['key_id'],
                algorithm=sig_result['algorithm'],
                user_id=user_id,
            )

            result['stages']['digital_signature'] = sig_result

            if timing_mode and _t_stage is not None:
                stage_timings['digital_signature_ms'] = round(
                    (time.perf_counter() - _t_stage) * 1000, 2
                )

        # ========================================
        # STAGE 4: ACCESS CONTROL (if user provided)
        # ========================================
        _t_stage = time.perf_counter() if timing_mode else None
        if user_id:
            print("\n🛡️  STAGE 4: ACCESS CONTROL CHECK")
            print("-" * 80)
            
            user = self.rbac.get_user(user_id)
            if user:
                print(f"   User:                  {user.name} ({user_id})")
                print(f"   Access Level:          Level {user.access_level} ({user.role})")
                print(f"   Document Class:        {classification}")
                
                # Check access permission
                access_result = self.rbac.check_access(user_id, classification, 'view')
                has_access = access_result.get('allowed', False)

                if has_access:
                    print(f"   Access Decision:       ✅ GRANTED")
                    
                    # If document is encrypted, decrypt it
                    if result['stages']['encryption']['encrypted']:
                        print(f"\n   🔓 Decrypting document...")

                        encrypted_info = result['stages']['encryption']
                        decrypted_text = self.pqc.decrypt(
                            encrypted_info['ciphertext'],
                            encrypted_info['key_id'],
                            encrypted_info['encapsulated_key'],
                            encrypted_info['nonce'],
                            encrypted_info.get('shared_secret')
                        )
                        
                        print(f"   Decryption:            ✅ SUCCESS")
                        print(f"   Content Preview:       {decrypted_text[:50]}...")
                        
                        result['stages']['access'] = {
                            'user_id': user_id,
                            'granted': True,
                            'decrypted': True,
                            'content': decrypted_text
                        }
                    else:
                        result['stages']['access'] = {
                            'user_id': user_id,
                            'granted': True,
                            'decrypted': False,
                            'content': text
                        }
                    
                    # Log access granted
                    self.audit.log_event(
                        event_type="ACCESS_GRANTED",
                        data={
                            'document_id': doc_id,
                            'user_id': user_id,
                            'classification': classification,
                            'user_level': user.access_level
                        }
                    )
                else:
                    print(f"   Access Decision:       ❌ DENIED")
                    print(f"   Reason:                Insufficient access level")
                    
                    result['stages']['access'] = {
                        'user_id': user_id,
                        'granted': False,
                        'reason': 'Insufficient access level'
                    }
                    
                    # Log access denied
                    self.audit.log_event(
                        event_type="ACCESS_DENIED",
                        data={
                            'document_id': doc_id,
                            'user_id': user_id,
                            'classification': classification,
                            'user_level': user.access_level
                        }
                    )
            else:
                print(f"   Error:                 ❌ User {user_id} not found")
                result['stages']['access'] = {
                    'user_id': user_id,
                    'granted': False,
                    'reason': 'User not found'
                }

        if timing_mode and _t_stage is not None:
            stage_timings['access_control_ms'] = round((time.perf_counter() - _t_stage) * 1000, 2)

        # ========================================
        # STAGE 4.5: INTEGRITY VERIFICATION (if protection enabled)
        # ========================================
        if enable_blockchain_protection:
            _t_stage = time.perf_counter() if timing_mode else None
            print("\n🔍 STAGE 4.5: BLOCKCHAIN INTEGRITY VERIFICATION")
            print("-" * 80)

            protection_chain = DocumentProtectionChain(
                storage_dir=Config.STORAGE_DIR,
            )
            verify_result = protection_chain.verify_document(
                doc_id=doc_id,
                content=text,
                classification=classification,
                metadata={
                    'classification_method': classification_result['method'],
                    'triggers': classification_result.get('triggers', []),
                    'confidence': classification_result.get('confidence'),
                },
            )

            if verify_result.get('verified'):
                print(f"   Integrity:             ✅ VERIFIED")
            else:
                print(f"   Integrity:             ❌ FAILED - {verify_result.get('error', verify_result.get('warning', 'Unknown'))}")
            print(f"   Verification Time:     {verify_result.get('elapsed_ms', 0):.2f} ms")

            result['stages']['integrity_verification'] = verify_result

            if timing_mode and _t_stage is not None:
                stage_timings['integrity_verification_ms'] = round(
                    (time.perf_counter() - _t_stage) * 1000, 2
                )

        # ========================================
        # STAGE 4.5b: DIGITAL SIGNATURE VERIFICATION
        # ========================================
        if enable_digital_signature:
            _t_stage = time.perf_counter() if timing_mode else None
            print("\n🔍 STAGE 4.5b: DIGITAL SIGNATURE VERIFICATION")
            print("-" * 80)

            sig_manager = DocumentSignatureManager()
            sig_verify = sig_manager.verify_signature(
                doc_id=doc_id,
                content=text,
                classification=classification,
                metadata={
                    'classification_method': classification_result['method'],
                    'triggers': classification_result.get('triggers', []),
                    'confidence': classification_result.get('confidence'),
                },
            )

            if sig_verify.get('verified'):
                print(f"   Integrity:             ✅ VERIFIED")
                print(f"   Signature Valid:       ✅ YES")
            else:
                print(f"   Integrity:             ❌ FAILED - {sig_verify.get('error', sig_verify.get('warning', 'Unknown'))}")
            print(f"   Verification Time:     {sig_verify.get('elapsed_ms', 0):.2f} ms")

            result['stages']['signature_verification'] = sig_verify

            if timing_mode and _t_stage is not None:
                stage_timings['signature_verification_ms'] = round(
                    (time.perf_counter() - _t_stage) * 1000, 2
                )

        # ========================================
        # STAGE 5: AUDIT TRAIL VERIFICATION
        # ========================================
        _t_stage = time.perf_counter() if timing_mode else None
        print("\n📋 STAGE 5: AUDIT TRAIL")
        print("-" * 80)
        
        # Verify chain integrity
        is_valid = self.audit.verify_chain_integrity()['valid']
        
        print(f"   Total Events Logged:   {len(self.audit.logs)}")
        print(f"   Chain Integrity:       {'✅ VALID' if is_valid else '❌ COMPROMISED'}")
        print(f"   Hash Algorithm:        SHA-256")
        print(f"   Last Event:            {self.audit.logs[-1].event_type if self.audit.logs else 'None'}")
        
        result['stages']['audit'] = {
            'total_events': len(self.audit.logs),
            'chain_valid': is_valid
        }

        if timing_mode and _t_stage is not None:
            stage_timings['audit_ms'] = round((time.perf_counter() - _t_stage) * 1000, 2)

        # Attach stage timings if in timing mode
        if timing_mode:
            result['stage_timings'] = stage_timings

        print("\n" + "=" * 80)
        print(f"✅ DOCUMENT PROCESSING COMPLETE: {doc_id}")
        print("=" * 80)

        return result
    
    def process_batch(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Process multiple documents in batch
        
        Args:
            documents: List of dicts with 'doc_id' and 'text' keys
            
        Returns:
            List of processing results
        """
        print("\n" + "🔥" * 40)
        print(f"🚀 BATCH PROCESSING: {len(documents)} DOCUMENTS")
        print("🔥" * 40 + "\n")
        
        results = []
        for doc in documents:
            result = self.process_document(
                doc_id=doc['doc_id'],
                text=doc['text'],
                user_id=doc.get('user_id')
            )
            results.append(result)
            print()  # Add spacing between documents
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics"""

        # Count documents by classification
        all_files = os.listdir(Config.STORAGE_DIR) if os.path.exists(Config.STORAGE_DIR) else []
        storage_files = [f for f in all_files if f.endswith('.json')]

        classifications = {'C0': 0, 'C1': 0, 'C2': 0, 'C3': 0}
        encrypted_count = 0

        for filename in storage_files:
            with open(os.path.join(Config.STORAGE_DIR, filename), 'r') as f:
                data = json.load(f)
                classifications[data['classification']] = classifications.get(data['classification'], 0) + 1
                if data.get('encrypted_data'):
                    encrypted_count += 1
        
        # Audit stats
        audit_stats = {
            'total_events': len(self.audit.logs),
            'chain_valid': self.audit.verify_chain_integrity()['valid']
        }
        
        # Count event types
        event_types = {}
        for log in self.audit.logs:
            event_type = log.event_type
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        return {
            'documents_processed': self.doc_counter,
            'documents_stored': len(storage_files),
            'classifications': classifications,
            'encrypted_documents': encrypted_count,
            'audit': audit_stats,
            'event_types': event_types
        }
    
    def display_statistics(self):
        """Display formatted statistics"""
        stats = self.get_statistics()
        
        print("\n" + "📊" * 40)
        print("📊 PIPELINE STATISTICS")
        print("📊" * 40 + "\n")
        
        print("📄 DOCUMENTS:")
        print(f"   Total Processed:       {stats['documents_processed']}")
        print(f"   Total Stored:          {stats['documents_stored']}")
        print()
        
        print("🎯 CLASSIFICATIONS:")
        for level, count in stats['classifications'].items():
            print(f"   {level}:                     {count}")
        print()
        
        print("🔐 ENCRYPTION:")
        print(f"   Encrypted Documents:   {stats['encrypted_documents']}")
        print(f"   Plaintext Documents:   {stats['documents_stored'] - stats['encrypted_documents']}")
        print()
        
        print("📋 AUDIT TRAIL:")
        print(f"   Total Events:          {stats['audit']['total_events']}")
        print(f"   Chain Integrity:       {'✅ VALID' if stats['audit']['chain_valid'] else '❌ COMPROMISED'}")
        print()
        
        print("🎬 EVENT TYPES:")
        for event_type, count in stats['event_types'].items():
            print(f"   {event_type:20s} {count}")
        
        print("\n" + "=" * 80 + "\n")


# ============================================================================
# INPUT METHODS
# ============================================================================

def load_documents_from_file(filepath: str) -> List[Dict[str, str]]:
    """
    Load documents from JSON file
    
    Expected format:
    [
        {
            "doc_id": "DOC_001",
            "text": "Document content here...",
            "user_id": "U002"  # Optional
        },
        ...
    ]
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        print(f"✅ Loaded {len(documents)} documents from {filepath}\n")
        return documents
    except FileNotFoundError:
        print(f"❌ Error: File '{filepath}' not found")
        return []
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON format in '{filepath}'")
        return []


def interactive_mode(pipeline: DocumentPipeline):
    """
    Interactive mode - add documents one by one
    """
    print("\n" + "🎮" * 40)
    print("🎮 INTERACTIVE MODE")
    print("🎮" * 40 + "\n")
    
    documents = []
    
    while True:
        print("\n" + "-" * 80)
        print("📝 Enter Document Details (or type 'done' to finish)")
        print("-" * 80)
        
        # Get document ID
        doc_id = input("Document ID (e.g., DOC_001): ").strip()
        if doc_id.lower() == 'done':
            break
        
        if not doc_id:
            print("⚠️  Document ID cannot be empty. Try again.")
            continue
        
        # Get document text
        print("\nDocument Text (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                lines.pop()  # Remove the last empty line
                break
            lines.append(line)
        
        text = "\n".join(lines).strip()
        
        if not text:
            print("⚠️  Document text cannot be empty. Try again.")
            continue
        
        # Get user ID (optional)
        print("\nUser ID for access test (optional, press Enter to skip): ", end="")
        user_id = input().strip() or None
        
        # Confirm
        print(f"\n✅ Document '{doc_id}' added!")
        print(f"   Text length: {len(text)} characters")
        if user_id:
            print(f"   Will test access for user: {user_id}")
        
        documents.append({
            'doc_id': doc_id,
            'text': text,
            'user_id': user_id
        })
        
        print(f"\nTotal documents: {len(documents)}")
    
    if not documents:
        print("\n⚠️  No documents to process. Exiting.")
        return
    
    # Process all documents
    print(f"\n🚀 Processing {len(documents)} document(s)...\n")
    pipeline.process_batch(documents)

    # Display statistics
    pipeline.display_statistics()
    
    # Audit logs are auto-saved
    print("✅ Audit logs saved to audit_logs/ directory\n")


def display_menu():
    """Display main menu"""
    print("\n" + "=" * 80)
    print("🏦 POLICY-AWARE HYBRID AI DOCUMENT CLASSIFICATION SYSTEM")
    print("    Coventry University - The Knowledge Hub")
    print("    Student: Noor Elhemaly (202300013)")
    print("    Advisor: Dr. Haitham Ghalwash")
    print("=" * 80 + "\n")
    
    print("📋 SELECT INPUT METHOD:")
    print("   1. Interactive Mode (Enter documents manually)")
    print("   2. Load from JSON file")
    print("   3. Load from dataset (synthetic_training_dataset.json)")
    print("   4. Load from test dataset (diverse_test_dataset.json)")
    print("   5. Exit")
    print()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    
    # Initialize pipeline
    pipeline = DocumentPipeline()
    
    while True:
        display_menu()
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            # Interactive mode
            interactive_mode(pipeline)
            
        elif choice == '2':
            # Load from custom JSON file
            filepath = input("\nEnter JSON file path: ").strip()
            documents = load_documents_from_file(filepath)
            
            if documents:
                # Map 'id' to 'doc_id' and generate IDs if missing
                documents = [
                    {'doc_id': doc.get('id', doc.get('doc_id', f'DOC_{i+1:03d}')), 'text': doc['text']}
                    for i, doc in enumerate(documents)
                ]
                pipeline.process_batch(documents)
                pipeline.display_statistics()
                print("✅ Audit logs saved to audit_logs/ directory\n")

            input("\nPress Enter to continue...")

        elif choice == '3':
            # Load from synthetic training dataset
            filepath = os.path.join(Config.DATA_DIR, "synthetic_training_dataset.json")

            if not os.path.exists(filepath):
                print(f"\n⚠️  File '{filepath}' not found in current directory.")
                print("   Please make sure the file exists or choose another option.")
                input("\nPress Enter to continue...")
                continue
            
            # Ask how many documents to process
            print(f"\nFound: {filepath}")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    all_docs = json.load(f)
                
                print(f"Total documents in file: {len(all_docs)}")
                
                num_docs = input(f"How many documents to process? (1-{len(all_docs)}, or 'all'): ").strip()
                
                if num_docs.lower() == 'all':
                    documents = all_docs
                else:
                    try:
                        num_docs = int(num_docs)
                        num_docs = min(num_docs, len(all_docs))  # Ensure we don't exceed available docs
                        documents = random.sample(all_docs, num_docs)
                        print(f"✅ Randomly selected {num_docs} documents")
                    except ValueError:
                        print("Invalid number. Randomly selecting 10 documents.")
                        documents = random.sample(all_docs, min(10, len(all_docs)))
                
                # Map 'id' to 'doc_id' for compatibility
                documents = [{'doc_id': doc.get('id', doc.get('doc_id')), 'text': doc['text']} for doc in documents]

                print(f"\n🚀 Processing {len(documents)} document(s)...\n")
                pipeline.process_batch(documents)
                pipeline.display_statistics()
                print("✅ Audit logs saved to audit_logs/ directory\n")

            except Exception as e:
                print(f"❌ Error processing file: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == '4':
            # Load from test dataset
            filepath = os.path.join(Config.DATA_DIR, "diverse_test_dataset.json")

            if not os.path.exists(filepath):
                print(f"\n⚠️  File '{filepath}' not found in current directory.")
                print("   Please make sure the file exists or choose another option.")
                input("\nPress Enter to continue...")
                continue
            
            documents = load_documents_from_file(filepath)

            if documents:
                # Map 'id' to 'doc_id' and generate IDs if missing
                documents = [
                    {'doc_id': doc.get('id', doc.get('doc_id', f'TEST_{i+1:03d}')), 'text': doc['text']}
                    for i, doc in enumerate(documents)
                ]

                # Optionally add user_id for access testing
                print("\n📋 Available Users:")
                for user in pipeline.rbac.users.values():
                    print(f"   {user.user_id}: {user.name} (Level {user.access_level} - {user.role})")

                print("\nAdd user ID for access testing?")
                user_id = input("User ID (or press Enter to skip): ").strip() or None

                if user_id:
                    for doc in documents:
                        doc['user_id'] = user_id

                pipeline.process_batch(documents)
                pipeline.display_statistics()
                print("✅ Audit logs saved to audit_logs/ directory\n")

            input("\nPress Enter to continue...")

        elif choice == '5':
            # Exit
            print("\n" + "=" * 80)
            print("👋 Thank you for using the Document Classification System!")
            print("=" * 80 + "\n")
            break
            
        else:
            print("\n⚠️  Invalid choice. Please select 1-5.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
