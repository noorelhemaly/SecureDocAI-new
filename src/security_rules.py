import re

class SecurityRules:
    """Pattern-based security rules for Egyptian banking"""

    def __init__(self):
        # National ID patterns - supports Egyptian, Qatar (QID), and generic formats
        # Egyptian format: 14 digits starting with 2 or 3
        # Qatar QID format: QID followed by 11 digits
        self.national_id_patterns = [
            re.compile(r'\b[23]\d{13}\b'),  # Egyptian format: 29912011234567
            re.compile(r'\bQ[I1]D[#:\s]*\d{10,12}\b', re.IGNORECASE),  # Qatar QID: QID#30681802683 (also handles OCR error Q1D)
            re.compile(r'\bnational\s*id[:\s#]*\d{6,14}\b', re.IGNORECASE),  # National ID: 123456789
            re.compile(r'\bid\s*(?:number|no\.?|#)[:\s]*\d{6,14}\b', re.IGNORECASE),  # ID Number: 123456789
            re.compile(r'\bرقم\s*(?:الهوية|البطاقة|القومي)[:\s#]*\d{6,14}'),  # Arabic: رقم الهوية: 123456789
            re.compile(r'\bID[:\s#]+\d{6,14}\b'),  # ID: 123456789 (uppercase ID)
        ]

        # Passport patterns - supports various formats including numbers in parentheses
        self.passport_patterns = [
            re.compile(r'\b[A-Z]{1,2}\d{7,8}\b'),  # A12345678 or AB1234567
            re.compile(r'\([A-Z]{1,2}\d{7,8}\)'),  # (A12345678) - in parentheses
            re.compile(r'\bpassport[:\s#]*\(?[A-Z0-9]{6,9}\)?', re.IGNORECASE),  # passport: A12345678 or (A12345678)
            re.compile(r'\bpassport\s*(?:number|no\.?|#)[:\s]*\(?[A-Z0-9]{6,9}\)?', re.IGNORECASE),  # Passport Number: (A12345678)
            re.compile(r'\bجواز[:\s#]*\(?[A-Z0-9]{6,9}\)?'),  # جواز سفر: A12345678
            re.compile(r'\bجواز\s*(?:سفر|السفر)[:\s#]*\(?[A-Z0-9]{6,9}\)?'),  # جواز السفر: A12345678
        ]

        # Egyptian IBAN: EG + 2 check digits + 25 characters
        self.iban_pattern = re.compile(r'\bEG\d{27}\b')

        # Salary patterns (multiple formats - EGP, USD, generic)
        self.salary_patterns = [
            # EGP formats
            re.compile(r'\b\d{4,6}\s*(?:EGP|egp|جنيه|ج\.م)\b'),  # 15000 EGP
            re.compile(r'\bsalary[:|\s]*\d{4,6}', re.IGNORECASE),  # Salary: 15000
            re.compile(r'\براتب[:|\s]*\d{4,6}'),  # راتب: 15000
            re.compile(r'\b\d{4,6}\s*(?:Egyptian Pounds?|pounds?)', re.IGNORECASE),
            # USD/Dollar formats
            re.compile(r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b'),  # $15,000 or $15000.00
            re.compile(r'\$\s*\d+[Kk]\b'),  # $15K or $15k
            re.compile(r'\b\d{1,3}(?:,\d{3})*\s*(?:USD|usd|dollars?)\b', re.IGNORECASE),  # 15000 USD
            # Monthly/Annual salary indicators
            re.compile(r'\b(?:monthly|annual)\s*(?:salary|compensation|pay)[:|\s]*\d{4,}', re.IGNORECASE),
            re.compile(r'\bcompensation[:|\s]*\d{4,}', re.IGNORECASE),
            re.compile(r'\b(?:base|gross|net)\s*salary[:|\s]*\d{4,}', re.IGNORECASE),
        ]
        
        # Personal data patterns
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'\b(?:01[0125]\d{8}|02\d{7,8})\b')

        # Masked/redacted data patterns - these indicate data has been sanitized
        self.masked_patterns = [
            re.compile(r'\*{3,}'),  # Three or more asterisks
            re.compile(r'X{3,}', re.IGNORECASE),  # Three or more X's
            re.compile(r'\[redacted\]', re.IGNORECASE),
            re.compile(r'\[masked\]', re.IGNORECASE),
            re.compile(r'partial\s*data', re.IGNORECASE),
            re.compile(r'بيانات\s*جزئية'),  # Arabic: partial data
        ]
        
        # Public keywords - customer-facing notices and announcements
        self.public_keywords = [
            'press release', 'public announcement', 'public notice',
            'holiday notice', 'bank holiday', 'service update',
            'career opportunity', 'job opening', 'job posting',
            'position available', 'apply now', 'we are hiring', 'careers@',
            # Customer-facing service notices
            'branches will be closed', 'branches closed', 'branch closure',
            'atm services', 'online banking',
            'working hours', 'opening hours', 'business hours',
            # Arabic public keywords
            'بيان صحفي', 'إعلان عام', 'عطلة رسمية',
            'فروع بنك', 'خدمات الصراف', 'ساعات العمل',
            'مغلقة بمناسبة',
        ]

        # Internal keywords - training, employee communications
        self.internal_keywords = [
            'meeting', 'minutes', 'internal', 'team',
            'operations', 'project', 'memo', 'memorandum',
            'training', 'تدريب', 'workshop', 'ورشة',
            'all employees', 'جميع الموظفين', 'staff only',
            'اجتماع', 'فريق', 'عمليات', 'مشروع'
        ]

        # Confidential business keywords (C2) - specific phrases only, not generic words
        # These indicate actual confidential business documents, not routine internal docs
        self.confidential_keywords = [
            'budget allocation', 'budget proposal', 'budget approval',
            'roi analysis', 'return on investment',
            'strategic goals', 'strategic plan', 'transformation strategy',
            'cost reduction plan', 'revenue projection', 'financial projection',
            'proprietary', 'not for distribution', 'do not share',
            'competitive analysis', 'market strategy', 'pricing strategy',
            'merger', 'acquisition', 'due diligence',
            'board confidential', 'executive only',
        ]
    
    def detect_national_id(self, text: str) -> bool:
        """Check if text contains National ID in various formats"""
        return any(pattern.search(text) for pattern in self.national_id_patterns)

    def detect_passport(self, text: str) -> bool:
        """Check if text contains Egyptian passport number"""
        return any(pattern.search(text) for pattern in self.passport_patterns)

    def detect_iban(self, text: str) -> bool:
        """Check if text contains Egyptian IBAN"""
        return bool(self.iban_pattern.search(text))

    def detect_salary(self, text: str) -> bool:
        """Check if text contains salary information (EGP, USD, or generic formats)"""
        return any(pattern.search(text) for pattern in self.salary_patterns)
    
    def detect_personal_data(self, text: str) -> tuple:
        """
        Check for personal data (email, phone)
        Returns: (has_email, has_phone)
        """
        has_email = bool(self.email_pattern.search(text))
        has_phone = bool(self.phone_pattern.search(text))
        return has_email, has_phone

    def detect_masked_data(self, text: str) -> bool:
        """
        Check if text contains masked/redacted data indicators.
        Documents with masked data should be downgraded from C3.
        """
        return any(pattern.search(text) for pattern in self.masked_patterns)
    
    def classify_by_rules(self, text: str) -> dict:
        """
        Classify document using security rules only
        
        Returns:
            {
                'classification': 'C0'|'C1'|'C2'|'C3',
                'confidence': float,
                'triggers': [list],
                'reasoning': str
            }
        """
        
        triggers = []

        # Check C3 triggers (PII and financial data)
        if self.detect_national_id(text):
            triggers.append('National ID')

        if self.detect_passport(text):
            triggers.append('Passport')

        if self.detect_iban(text):
            triggers.append('IBAN')

        if self.detect_salary(text):
            triggers.append('Salary')

        if triggers:
            return {
                'classification': 'C3',
                'confidence': None,  # AI determines confidence
                'triggers': triggers,
                'reasoning': f"Contains: {', '.join(triggers)}"
            }

        text_lower = text.lower()

        # Check for CV/Resume - these are always C2 (Personal Data)
        cv_indicators = ['curriculum vitae', 'resume', 'cv', 'experience', 'education',
                        'skills', 'work history', 'employment history', 'professional summary',
                        'السيرة الذاتية', 'الخبرات', 'المؤهلات']
        cv_score = sum(1 for indicator in cv_indicators if indicator in text_lower)
        has_email, has_phone = self.detect_personal_data(text)

        # If it looks like a CV (3+ indicators) and has contact info, it's C2
        if cv_score >= 3 and (has_email or has_phone):
            triggers.append('CV/Resume')
            return {
                'classification': 'C2',
                'confidence': None,
                'triggers': triggers,
                'reasoning': f'CV/Resume with personal contact information ({cv_score} CV indicators)'
            }

        # Check for internal keywords FIRST (training, meetings, etc.)
        internal_count = sum(1 for kw in self.internal_keywords
                           if kw.lower() in text_lower)
        is_internal_document = internal_count >= 1

        # Check for public keywords
        public_count = sum(1 for kw in self.public_keywords
                         if kw.lower() in text_lower)
        is_public_document = public_count >= 1 or 'press release' in text_lower or 'press@' in text_lower

        # Check for contract/agreement keywords (includes banking agreements)
        has_contract_keywords = any(kw in text_lower for kw in
                                   ['contract', 'employment agreement', 'employment contract',
                                    'account opening agreement', 'banking services agreement',
                                    'اتفاقية فتح حساب', 'إتفاقية فتح حساب',
                                    'عقد عمل', 'عقد توظيف'])

        # Check C2 triggers
        # Skip C2 check for internal docs (training, meetings have generic emails)
        # BUT always check C2 if contract keywords are present (contracts are C2)
        if has_contract_keywords or (not is_internal_document and not is_public_document):
            has_email, has_phone = self.detect_personal_data(text)
            # More specific name pattern - exclude common title words
            name_matches = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text)
            # Filter out common non-name patterns
            non_names = {'Risk Management', 'Training Announcement', 'Human Resources',
                        'Customer Service', 'Bank Misr', 'Annual Report', 'Service Update'}
            actual_names = [m for m in name_matches if m not in non_names]
            has_name = len(actual_names) > 0

            # Check for filled account/reference numbers (indicates a filled form, not blank)
            has_account_number = bool(re.search(r'\b\d{6,10}\b', text))

            # C2 if: (contract + contact) OR (name + contact in non-internal doc)
            # OR (banking agreement + filled customer name + account number)
            if (has_contract_keywords and (has_email or has_phone)) or \
               (not is_internal_document and has_name and (has_email or has_phone)) or \
               (has_contract_keywords and has_name and has_account_number):
                triggers.append('Personal Data')
                return {
                    'classification': 'C2',
                    'confidence': None,
                    'triggers': triggers,
                    'reasoning': 'Contains personal/contact information'
                }

        # Check for confidential business documents (C2)
        confidential_count = sum(1 for kw in self.confidential_keywords
                                if kw.lower() in text_lower)
        if confidential_count >= 2:
            triggers.append('Confidential Business')
            return {
                'classification': 'C2',
                'confidence': None,  # AI determines confidence
                'triggers': triggers,
                'reasoning': f'Confidential business document ({confidential_count} indicators)'
            }

        # Check C1 vs C0 - if both match, higher count wins
        if internal_count >= 1 and public_count >= 1:
            if public_count >= internal_count:
                return {
                    'classification': 'C0',
                    'confidence': None,
                    'triggers': ['Public keywords'],
                    'reasoning': f'Public indicators ({public_count}) >= Internal ({internal_count})'
                }
            else:
                return {
                    'classification': 'C1',
                    'confidence': None,
                    'triggers': ['Internal keywords'],
                    'reasoning': f'Internal indicators ({internal_count}) > Public ({public_count})'
                }

        # Only internal keywords matched
        if internal_count >= 1:
            return {
                'classification': 'C1',
                'confidence': None,
                'triggers': ['Internal keywords'],
                'reasoning': f'{internal_count} internal keywords found'
            }

        # Only public keywords matched
        if public_count >= 1:
            return {
                'classification': 'C0',
                'confidence': None,
                'triggers': ['Public keywords'],
                'reasoning': 'Public announcement indicators'
            }
        
        # No rules matched - let AI decide
        return {
            'classification': None,
            'confidence': None,
            'triggers': [],
            'reasoning': 'No rule triggers found, deferring to AI'
        }


def hybrid_classify(text: str, llm_result: dict, rules: SecurityRules) -> dict:
    """
    Combine LLM + Rules classification

    Strategy:
    1. Rules detect C3 → ALWAYS C3 (safety critical)
    2. Both agree → Use LLM classification
    3. Disagree → Use HIGHER classification (safer)

    Confidence always comes from AI (LLM)
    """

    rules_result = rules.classify_by_rules(text)

    llm_class = llm_result['classification']
    llm_confidence = llm_result.get('confidence')  # AI-determined confidence
    rules_class = rules_result['classification']

    # Handle ERROR from LLM
    if llm_class == 'ERROR':
        # If rules also found nothing, default to C1 (safest without AI)
        fallback = rules_class if rules_class is not None else 'C1'
        return {
            'classification': fallback,
            'confidence': None,
            'method': 'LLM_ERROR_USE_RULES',
            'llm_classification': 'ERROR',
            'rules_classification': rules_class,
            'reasoning': f"LLM error, using rules: {rules_result['reasoning']}",
            'agreement': False
        }

    # Rules found nothing → trust AI completely
    if rules_class is None:
        return {
            'classification': llm_class,
            'confidence': llm_confidence,
            'method': 'AI_DECISION',
            'llm_classification': llm_class,
            'rules_classification': None,
            'reasoning': llm_result.get('reasoning', 'AI classified, no rule triggers'),
            'agreement': True
        }

    hierarchy = {'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3}

    # ALWAYS trust rules for C3
    if rules_class == 'C3':
        return {
            'classification': 'C3',
            'confidence': llm_confidence,
            'method': 'RULES_OVERRIDE',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': f"Security rules: {rules_result['reasoning']}",
            'agreement': llm_class == rules_class
        }

    # Agreement
    if llm_class == rules_class:
        return {
            'classification': llm_class,
            'confidence': llm_confidence,
            'method': 'AGREEMENT',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': llm_result.get('reasoning', 'Agreement'),
            'agreement': True
        }

    # Disagreement → use higher
    if hierarchy[rules_class] > hierarchy[llm_class]:
        return {
            'classification': rules_class,
            'confidence': llm_confidence,
            'method': 'RULES_HIGHER',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': rules_result['reasoning'],
            'agreement': False
        }
    else:
        # Special case: LLM says C3 but rules don't detect actual PII
        # Check if data is masked/redacted - if so, downgrade to C2
        if llm_class == 'C3' and rules_class != 'C3' and rules.detect_masked_data(text):
            return {
                'classification': 'C2',
                'confidence': llm_confidence,
                'method': 'MASKED_DATA_DOWNGRADE',
                'llm_classification': llm_class,
                'rules_classification': rules_class,
                'reasoning': 'Document contains masked/redacted PII - downgraded from C3 to C2',
                'agreement': False
            }

        return {
            'classification': llm_class,
            'confidence': llm_confidence,
            'method': 'LLM_HIGHER',
            'llm_classification': llm_class,
            'rules_classification': rules_class,
            'reasoning': llm_result.get('reasoning', 'LLM higher'),
            'agreement': False
        }


if __name__ == "__main__":
    # Test the rules
    rules = SecurityRules()

    tests = [
        # C0 - Public
        ("Holiday announcement", "C0"),
        ("Press release: New branch opening", "C0"),
        # C1 - Internal
        ("Meeting about operations", "C1"),
        ("Internal memo: Team restructuring", "C1"),
        # C2 - Confidential
        ("Contract for sara@bank.com", "C2"),
        ("Employment agreement with Ahmed Mohamed, phone: 01012345678", "C2"),
        # C3 - National ID
        ("National ID: 29912011234567", "C3"),
        ("الرقم القومي: 29001011234567", "C3"),
        # C3 - Passport
        ("Passport: A12345678", "C3"),
        ("جواز سفر: AB1234567", "C3"),
        # C3 - IBAN
        ("IBAN: EG380019000500000000263180002", "C3"),
        # C3 - Salary (EGP)
        ("Salary 15000 EGP", "C3"),
        ("راتب: 25000 جنيه", "C3"),
        # C3 - Salary (USD)
        ("Employee salary: $45K", "C3"),
        ("Annual compensation: $120,000 USD", "C3"),
        ("Monthly salary: $5,500", "C3"),
        # Mixed Arabic/English C3
        ("شهادة راتب - Employee: Ahmed, National ID: 29901151234567, الراتب: 18000 EGP", "C3"),
        # Masked/Redacted data - should NOT trigger C3 (rules don't match masked data)
        ("Customer: Ahmed M., Phone: 010****5678, Account: EG38****002 - partial data", "C1"),
        ("IBAN: EG38XXXXXXXXXXXXXXXXXXXX002 [redacted]", "C1"),
        ("National ID: 299*****1234567 - بيانات جزئية", "C1"),
    ]

    print("Testing Security Rules:")
    print("=" * 60)

    passed = 0
    for text, expected in tests:
        result = rules.classify_by_rules(text)
        correct = result['classification'] == expected
        if correct:
            passed += 1
        print(f"\n{text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"Expected: {expected}, Got: {result['classification']} {'✓' if correct else '✗'}")
        print(f"Triggers: {result['triggers']}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{len(tests)} tests passed")