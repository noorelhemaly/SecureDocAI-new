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
    USERS_FILE = os.path.join(BASE_DIR, "config", "rbac_users.json")
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

        self.system_prompt = """You are a document classification assistant for an Egyptian financial institution.
Classify documents into exactly one of these security levels:

- C0 (Public): Press releases, public announcements, job postings, service updates, holiday notices, training materials, policy documents, educational content

- C1 (Internal): Internal memos, meeting minutes (routine), department communications, project updates, team info, non-sensitive internal documents

- C2 (Confidential): Employment contracts, non-executive agreements, confidential business documents, personal employee data (without sensitive details), routine confidential correspondence

- C3 (Highly Sensitive): Documents requiring maximum protection, including:
  * **Personal Identifiable Information (PII)**: Actual National ID numbers, passport numbers, real IBAN/account numbers, credit card numbers
  * **Financial Data**: Specific salary/payroll amounts, executive compensation packages, stock options, bonuses, financial credentials, account balances
  * **Strategic Information**: M&A (merger/acquisition) plans, board meeting minutes with strategic decisions, business acquisition targets, confidential negotiations
  * **Trade Secrets & IP**: Proprietary algorithms, trading strategies, product formulas, confidential research, competitive intelligence
  * **Security & Risk**: Security vulnerabilities, data breach reports, fraud investigations, incident reports with sensitive details, penetration test results
  * **Legal & Regulatory**: Legal disputes, litigation documents, regulatory violations, compliance issues, internal investigations
  * **Customer Data**: Large-scale customer databases, bulk customer financial information (account balances, assets under management), customer lists with competitive intelligence value, high-value client portfolios
  * **Executive/Board Level**: CEO/executive private communications with sensitive content, confidential board decisions

CRITICAL CLASSIFICATION RULES:
1. **Context Over Keywords**: Distinguish between MENTIONING sensitive terms vs CONTAINING actual sensitive data
   - "Training on how to protect National IDs" → C0 (educational)
   - "Employee National ID: 29012851201234" → C3 (actual sensitive data)

2. **Intent Analysis**: Consider the document's purpose
   - Policy/training about confidentiality → C0 or C1
   - Actual confidential information → C2 or C3

3. **Specificity Check**: Look for real data vs generic references
   - "IBAN format: EGXXXXXXXXXXXXXXXXX" → C0/C1 (example)
   - "IBAN: EG380019000100123456789012345" → C3 (real account)
   - "Salary: competitive" → C0/C1 (generic)
   - "Salary: 15,000 EGP" → C3 (specific amount)

4. **Document Type Recognition**:
   - Training materials, policies, procedures → Usually C0 or C1
   - Templates with placeholders → C0 or C1
   - Filled forms with real data → C2 or C3

5. **Public Declaration**: If document explicitly states it's public/for all employees → Strong indicator for C0

6. **C2 vs C3 Distinction**: Critical decision point
   C2 (Confidential):
   - Standard employee contracts without specific financial amounts
   - Routine confidential business correspondence
   - General business agreements
   - Non-executive personal data

   C3 (Highly Sensitive) - Requires ANY of:
   - Actual PII (National IDs, IBANs, passport numbers, account numbers)
   - Specific financial amounts (salaries, bonuses, account balances)
   - Strategic business decisions (M&A, acquisitions, board decisions)
   - Trade secrets or proprietary information
   - Security incidents, breaches, vulnerabilities, fraud
   - Legal disputes, regulatory violations
   - Executive/board level communications with sensitive content

   Rule of thumb: If disclosure could cause:
   - C2: Business embarrassment, competitive disadvantage
   - C3: Severe financial loss, legal liability, regulatory action, or individual harm

CONFIDENCE SCORING:
- 0.95-1.0: Very confident (clear indicators, unambiguous)
- 0.80-0.94: Confident (strong indicators, minor ambiguity)
- 0.60-0.79: Moderate (some indicators, contextual judgment needed)
- 0.40-0.59: Low confidence (ambiguous, could go either way)

You MUST respond with ONLY valid JSON in this exact format (no other text):
{"classification": "C0", "confidence": 0.95, "reasoning": "brief explanation"}

Replace C0 with the appropriate level (C0, C1, C2, or C3) and confidence with your actual confidence level."""

        # Fallback keywords for when Ollama is not available
        self.fallback_keywords = {
            'C0': ['announcement', 'public', 'holiday', 'press release', 'service update', 'job opening'],
            'C1': ['internal', 'meeting', 'minutes', 'department', 'team', 'project', 'memo'],
            'C2': ['contract', 'employment', 'agreement', 'confidential'],
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

        # Check for C3 indicators first (highest priority)
        for keyword in self.fallback_keywords['C3']:
            if keyword in text_lower:
                return {
                    'classification': 'C3',
                    'confidence': None,  # No AI available
                    'reasoning': f'Fallback: Found sensitive keyword "{keyword}"'
                }

        # Check C2
        for keyword in self.fallback_keywords['C2']:
            if keyword in text_lower:
                return {
                    'classification': 'C2',
                    'confidence': None,  # No AI available
                    'reasoning': f'Fallback: Found confidential keyword "{keyword}"'
                }

        # Check C1
        for keyword in self.fallback_keywords['C1']:
            if keyword in text_lower:
                return {
                    'classification': 'C1',
                    'confidence': None,  # No AI available
                    'reasoning': f'Fallback: Found internal keyword "{keyword}"'
                }

        # Check C0
        for keyword in self.fallback_keywords['C0']:
            if keyword in text_lower:
                return {
                    'classification': 'C0',
                    'confidence': None,  # No AI available
                    'reasoning': f'Fallback: Found public keyword "{keyword}"'
                }

        # Default to C1 (Internal) if no keywords match
        return {
            'classification': 'C1',
            'confidence': None,  # No AI available
            'reasoning': 'Fallback: No clear indicators, defaulting to Internal'
        }

    def _classify_with_ollama(self, text: str) -> Dict[str, Any]:
        """Call Ollama API for classification - confidence comes from LLaMA"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"Classify this document:\n\n{text[:2000]}",
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent classification
                        "num_predict": 200
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            result_text = response.json().get("response", "")

            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                if result.get('classification') in ['C0', 'C1', 'C2', 'C3']:
                    # Use the confidence that LLaMA provided
                    confidence = float(result.get('confidence', 0.5))
                    # Clamp confidence between 0 and 1
                    confidence = max(0.0, min(1.0, confidence))

                    return {
                        'classification': result['classification'],
                        'confidence': confidence,
                        'reasoning': result.get('reasoning', 'LLaMA classification'),
                        'source': 'llama'
                    }

            # Fallback: extract classification from text if JSON parsing failed
            for level in ['C3', 'C2', 'C1', 'C0']:
                if level in result_text:
                    return {
                        'classification': level,
                        'confidence': None,  # AI didn't provide parseable confidence
                        'reasoning': 'Extracted from LLaMA response (JSON parse failed)',
                        'source': 'llama_fallback'
                    }

            # Could not parse - default to C1
            return {
                'classification': 'C1',
                'confidence': None,  # AI didn't provide parseable confidence
                'reasoning': 'Could not parse LLaMA response, defaulting to C1',
                'source': 'llama_error'
            }

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

    hierarchy = {'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3}

    # Rules found nothing → check if it's an empty template
    if rules_class is None:
        final_class = llm_class
        reasoning = llm_result.get('reasoning', 'AI classified, no rule triggers')

        # If LLM says C2 but it's likely an empty template, downgrade to C1
        if llm_class == 'C2' and is_likely_empty_template(text):
            final_class = 'C1'
            reasoning = f"Empty template/form detected - downgraded from C2 to C1 (no actual personal data). Original: {reasoning}"

        return {
            'classification': final_class,
            'confidence': llm_confidence,
            'method': 'AI_DECISION',
            'llm_classification': llm_class,
            'rules_classification': None,
            'reasoning': reasoning,
            'agreement': True,
            'triggers': []
        }

    # ALWAYS trust rules for C3 (safety-critical) - regardless of mode
    if rules_class == 'C3':
        return {
            'classification': 'C3',
            'confidence': llm_confidence,  # Use AI's confidence
            'method': 'RULES_OVERRIDE',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': f"Security rules detected C3 triggers: {', '.join(rules_result['triggers'])}",
            'agreement': llm_class == rules_class,
            'triggers': rules_result['triggers']
        }

    # Agreement - both classifiers agree
    if llm_class == rules_class:
        # For C3, always show the actual triggers detected (more accurate than LLM reasoning)
        triggers = rules_result.get('triggers', [])
        if llm_class == 'C3' and triggers:
            reasoning = f"Detected sensitive data: {', '.join(triggers)}"
        elif triggers:
            reasoning = f"{llm_result['reasoning']} (Triggers: {', '.join(triggers)})"
        else:
            reasoning = llm_result['reasoning']

        return {
            'classification': llm_class,
            'confidence': llm_confidence,  # Use AI's confidence
            'method': 'AGREEMENT',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': reasoning,
            'agreement': True,
            'triggers': triggers
        }

    # Disagreement - decision based on hybrid_mode
    if hybrid_mode == 'aggressive':
        # Aggressive: Trust LLM if confident enough
        if llm_confidence >= confidence_threshold:
            return {
                'classification': llm_class,
                'confidence': llm_confidence,
                'method': 'LLM_TRUSTED',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': f"LLM confident ({llm_confidence:.0%}): {llm_result['reasoning']}",
                'agreement': False,
                'triggers': rules_result.get('triggers', [])
            }

    elif hybrid_mode == 'balanced':
        # Balanced: Trust LLM if very confident, else use higher
        if llm_confidence >= confidence_threshold and hierarchy[llm_class] >= hierarchy[rules_class]:
            return {
                'classification': llm_class,
                'confidence': llm_confidence,
                'method': 'LLM_CONFIDENT',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': llm_result['reasoning'],
                'agreement': False,
                'triggers': rules_result.get('triggers', [])
            }

    # Conservative mode OR fallback: use higher classification if auto_escalate is True
    if auto_escalate:
        if hierarchy[rules_class] > hierarchy[llm_class]:
            return {
                'classification': rules_class,
                'confidence': llm_confidence,  # Use AI's confidence
                'method': 'RULES_ESCALATED',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': f"Escalated to rules classification: {rules_result['reasoning']}",
                'agreement': False,
                'triggers': rules_result['triggers']
            }
        else:
            # Special case: LLM says C3 but rules don't detect actual PII
            # Check if data is masked/redacted - if so, downgrade to C2
            if llm_class == 'C3' and rules_class != 'C3' and security_rules.detect_masked_data(text):
                return {
                    'classification': 'C2',
                    'confidence': llm_confidence,  # Use AI's confidence
                    'method': 'MASKED_DATA_DOWNGRADE',
                    'llm_classification': llm_class,
                    'rules_classification': rules_class,
                    'reasoning': 'Document contains masked/redacted PII - downgraded from C3 to C2',
                    'agreement': False,
                    'triggers': ['Masked Data']
                }

            # Special case: LLM says C2 but rules detect internal document (training, meeting, etc.)
            # Trust rules - internal documents shouldn't be escalated to C2 just because of generic emails
            if llm_class == 'C2' and rules_class == 'C1' and 'Internal keywords' in rules_result.get('triggers', []):
                return {
                    'classification': 'C1',
                    'confidence': llm_confidence,  # Use AI's confidence
                    'method': 'INTERNAL_DOC_OVERRIDE',
                    'llm_classification': llm_class,
                    'rules_classification': rules_class,
                    'reasoning': f"Internal document detected: {rules_result['reasoning']}",
                    'agreement': False,
                    'triggers': rules_result.get('triggers', [])
                }

            return {
                'classification': llm_class,
                'confidence': llm_confidence,  # Use AI's confidence
                'method': 'LLM_HIGHER',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': llm_result['reasoning'],
                'agreement': False,
                'triggers': rules_result.get('triggers', [])
            }
    else:
        # No auto-escalate: just use LLM result
        # Still check for masked data
        if llm_class == 'C3' and rules_class != 'C3' and security_rules.detect_masked_data(text):
            return {
                'classification': 'C2',
                'confidence': llm_confidence,  # Use AI's confidence
                'method': 'MASKED_DATA_DOWNGRADE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': 'Document contains masked/redacted PII - downgraded from C3 to C2',
                'agreement': False,
                'triggers': ['Masked Data']
            }
        return {
            'classification': llm_class,
            'confidence': llm_confidence,  # Use AI's confidence
            'method': 'LLM_NO_ESCALATE',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': llm_result['reasoning'],
            'agreement': False,
            'triggers': rules_result.get('triggers', [])
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
                for uid, user_data in users_data.items():
                    self.rbac.add_user(
                        user_id=user_data['user_id'],
                        name=user_data['name'],
                        access_level=user_data['access_level'],
                        role=user_data['role'],
                        department=user_data.get('department')
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
                         timing_mode: bool = False) -> Dict[str, Any]:
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

            storage_data = {
                'doc_id': doc_id,
                'classification': classification,
                'timestamp': result['timestamp'],
                'original_text': text if classification in ['C0', 'C1'] else None,
                'encrypted_data': result['stages']['encryption'] if result['stages']['encryption']['encrypted'] else None,
                'metadata': metadata
            }

            with open(storage_path, 'w', encoding='utf-8') as f:
                json.dump(storage_data, f, indent=2, ensure_ascii=False)

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
            protection_result = protection_chain.protect_document(
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
    results = pipeline.process_batch(documents)
    
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
                results = pipeline.process_batch(documents)
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
                results = pipeline.process_batch(documents)
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

                results = pipeline.process_batch(documents)
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
