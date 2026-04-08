#!/usr/bin/env python3
"""
Document Redaction Engine
Automatically redacts sensitive fields based on the viewing user's role and department.

References:
  - Egypt Labor Law No. 14/2025: HR must retain National ID, Passport, salary records.
  - Egypt PDPL Law No. 151/2020: sensitive personal/financial data requires lawful purpose.
  - CBE Financial Cybersecurity Framework (2020): need-to-know, least privilege.
  - ISO 27001:2022 Annex A 5.15: access only to data the role functionally requires.
"""

import re
from typing import List, Tuple


# ── Replacement labels shown in place of redacted values ──────────────────────
REDACT_LABEL = {
    'national_id': '[NATIONAL ID REDACTED]',
    'passport':    '[PASSPORT REDACTED]',
    'iban':        '[IBAN REDACTED]',
    'salary':      '[SALARY REDACTED]',
    'phone':       '[PHONE REDACTED]',
    'email':       '[EMAIL REDACTED]',
}

# ── Patterns (mirrors SecurityRules, kept here to avoid circular imports) ──────
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # National ID — Egyptian 14-digit, QID, keyword-prefixed
    ('national_id', re.compile(r'\b[23]\d{13}\b')),
    ('national_id', re.compile(r'\bQ[I1]D[#:\s]*\d{10,12}\b', re.IGNORECASE)),
    ('national_id', re.compile(r'\bnational\s*id[:\s#]*\d{6,14}\b', re.IGNORECASE)),
    ('national_id', re.compile(r'\bid\s*(?:number|no\.?|#)[:\s]*\d{6,14}\b', re.IGNORECASE)),
    ('national_id', re.compile(r'\bرقم\s*(?:الهوية|البطاقة|القومي)[:\s#]*\d{6,14}')),
    ('national_id', re.compile(r'\bID[:\s#]+\d{6,14}\b')),

    # Passport
    ('passport', re.compile(r'\b[A-Z]{1,2}\d{7,8}\b')),
    ('passport', re.compile(r'\([A-Z]{1,2}\d{7,8}\)')),
    ('passport', re.compile(r'\bpassport[:\s#]*\(?[A-Z0-9]{6,9}\)?', re.IGNORECASE)),
    ('passport', re.compile(r'\bpassport\s*(?:number|no\.?|#)[:\s]*\(?[A-Z0-9]{6,9}\)?', re.IGNORECASE)),
    ('passport', re.compile(r'\bجواز[:\s#]*\(?[A-Z0-9]{6,9}\)?')),
    ('passport', re.compile(r'\bجواز\s*(?:سفر|السفر)[:\s#]*\(?[A-Z0-9]{6,9}\)?')),

    # IBAN — Egyptian format EG + 27 digits
    ('iban', re.compile(r'\bEG\d{27}\b')),

    # Salary
    ('salary', re.compile(r'\b\d{4,6}\s*(?:EGP|egp|جنيه|ج\.م)\b')),
    ('salary', re.compile(r'\bsalary[:|\s]*\d{4,6}', re.IGNORECASE)),
    ('salary', re.compile(r'\براتب[:|\s]*\d{4,6}')),
    ('salary', re.compile(r'\b\d{4,6}\s*(?:Egyptian Pounds?|pounds?)', re.IGNORECASE)),
    ('salary', re.compile(r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b')),
    ('salary', re.compile(r'\$\s*\d+[Kk]\b')),
    ('salary', re.compile(r'\b\d{1,3}(?:,\d{3})*\s*(?:USD|usd|dollars?)\b', re.IGNORECASE)),
    ('salary', re.compile(r'\b(?:monthly|annual)\s*(?:salary|compensation|pay)[:|\s]*\d{4,}', re.IGNORECASE)),
    ('salary', re.compile(r'\bcompensation[:|\s]*\d{4,}', re.IGNORECASE)),
    ('salary', re.compile(r'\b(?:base|gross|net)\s*salary[:|\s]*\d{4,}', re.IGNORECASE)),

    # Phone — Egyptian mobile/landline
    ('phone', re.compile(r'\b(?:01[0125]\d{8}|02\d{7,8})\b')),

    # Email
    ('email', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
]


class DocumentRedactor:
    """
    Redacts sensitive fields from document text based on a user's
    role and department, as resolved by the RBACSystem.
    """

    def redact(self, text: str, field_visibility: dict) -> dict:
        """
        Apply redaction to *text* given a pre-resolved field_visibility map.

        Args:
            text:             Plain text to redact.
            field_visibility: Dict[field_type, bool] from
                              RBACSystem.get_field_visibility(user_id).

        Returns:
            {
              'redacted_text': str,
              'redacted_fields': List[str],   # which field types were redacted
              'redaction_count': int,
            }
        """
        redacted_fields = set()
        result = text

        for field_type, pattern in _PATTERNS:
            # Skip fields the user is allowed to see
            if field_visibility.get(field_type, False):
                continue

            label = REDACT_LABEL[field_type]

            def _replace(m, _label=label, _field=field_type):
                redacted_fields.add(_field)
                return _label

            result = pattern.sub(_replace, result)

        return {
            'redacted_text':   result,
            'redacted_fields': sorted(redacted_fields),
            'redaction_count': sum(
                len(pattern.findall(text))
                for ft, pattern in _PATTERNS
                if not field_visibility.get(ft, False)
            ),
        }
