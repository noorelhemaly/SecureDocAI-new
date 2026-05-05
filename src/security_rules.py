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

        # Passport patterns — require explicit context word to avoid false-positives
        # on financial codes (e.g. ISO currency codes + numbers in annual reports)
        self.passport_patterns = [
            # Must have the word "passport" or Arabic equivalent nearby
            re.compile(r'\bpassport[:\s#]*\(?[A-Z]{1,2}\d{7,8}\)?', re.IGNORECASE),
            re.compile(r'\bpassport\s*(?:number|no\.?|#)[:\s]*\(?[A-Z]{1,2}\d{7,8}\)?', re.IGNORECASE),
            re.compile(r'\bجواز[:\s#]*\(?[A-Z]{1,2}\d{7,8}\)?'),
            re.compile(r'\bجواز\s*(?:سفر|السفر)[:\s#]*\(?[A-Z]{1,2}\d{7,8}\)?'),
            # Bare passport number in parentheses (common in Egyptian KYC forms)
            re.compile(r'\([A-Z]{1,2}\d{7,8}\)'),
        ]

        # Egyptian IBAN: EG + 2 check digits + 25 digits = 29 chars total.
        # Only match FULL IBANs with actual digits — masked IBANs ("EG****") are NOT C3
        # because the sensitive number is hidden. A masked IBAN → C2 at most (masked data).
        # Also match "IBAN: EG..." keyword form when followed by real digits (not asterisks).
        self.iban_pattern = re.compile(
            r'\bEG\d{27}\b'                      # full Egyptian IBAN: EG + 27 digits
            r'|\bIBAN\s*[:\(]?\s*EG\d{4,}'       # "IBAN: EG80000..." — keyword + real digits
        )

        # Scale words that indicate aggregate financial figures, not personal salary
        _scale = r'(?!\s*(?:million|billion|trillion|M\b|B\b|bn\b|mn\b|مليون|مليار))'

        # Salary patterns (multiple formats - EGP, USD, generic)
        # NOTE: patterns use negative lookahead _scale to avoid false-positives on
        #       financial report tables where "$1,234 million" is aggregate data.
        self.salary_patterns = [
            # EGP formats — require explicit salary/pay context word + number + currency.
            # Bare "15000 EGP" without a salary keyword is NOT used: it fires on
            # financial report figures (fees, dividends, EPS values) when OCR drops commas.
            re.compile(r'\bsalary\s*(?:amount|:)\s*\d{4,6}', re.IGNORECASE),  # Salary amount: 15000
            re.compile(r'\b(?:salary|راتب)\s*(?:amount|:)?\s*\d{4,6}\s*(?:EGP|egp|جنيه|ج\.م)', re.IGNORECASE),
            re.compile(r'\براتب\s*(?:الموظف|الشهري|الأساسي)?[:|\s]*\d{4,6}'),  # راتب: 15000
            re.compile(r'\bnet\s+monthly\s+salary[:|\s]*\d{4,}', re.IGNORECASE),  # net monthly salary: 15000
            # "Egyptian Pounds" written out — very unlikely to appear in a financial report table
            re.compile(r'\b\d{4,6}\s*(?:Egyptian Pounds?)\b', re.IGNORECASE),
            # USD/Dollar formats — only with salary/compensation context word OR K suffix
            # The bare $amount pattern is too broad for financial reports
            re.compile(r'\$\s*\d+[Kk]\b'),  # $15K or $15k — K suffix implies personal scale
            re.compile(r'\b(?:salary|compensation|pay|remuneration)\s+of\s+\$\s*\d{1,3}(?:,\d{3})*' + _scale, re.IGNORECASE),
            # Monthly/Annual salary with explicit salary/pay keyword — require "net/gross/base" OR "monthly"
            re.compile(r'\b(?:monthly|net|gross|base)\s+salary[:|\s]*\d{4,}', re.IGNORECASE),
            re.compile(r'\b(?:base|gross|net)\s+(?:salary|pay|compensation)[:|\s]*\d{4,}', re.IGNORECASE),
            # "salary is EGP 14,750" / "salary of EGP 11,000" — EGP comes before the number.
            # Uses + (not *) on comma groups to prevent backtracking: "EGP 50,000 million"
            # fails the scale check on "50,000", cannot backtrack to "EGP 50" (2 digits
            # without a comma group → no match). Bare 4-6 digit form also accepted.
            re.compile(
                r'\b(?:salary|pay|compensation)\s+(?:is|of)\s+EGP\s+'
                r'(?:\d{1,3}(?:[,،]\d{3})+'   # comma-formatted: 14,750
                r'|\d{4,6})'                    # no-comma form: 14750
                + _scale, re.IGNORECASE),
            # "exact salary" / "exact net monthly salary" — unambiguous personal salary language.
            # Never appears in public financial reports or aggregate disclosures.
            re.compile(r'\bexact\s+(?:\w+\s+){0,3}salary\b', re.IGNORECASE),
            # Payslip / payroll format: "Basic Salary: EGP 18,500" / "Net Monthly Salary: EGP 22,590"
            # EGP appears AFTER the label but BEFORE the number (opposite of some formats above).
            # Require a salary/pay label word before EGP to avoid firing on fee tables.
            # Use \d[\d,،]* to match comma-formatted numbers like 22,590 or 18,500.
            re.compile(
                r'\b(?:basic|gross|net|base|total)\s+(?:salary|pay|compensation)'
                r'\s*[:\s]+EGP\s+\d[\d,،]*'
                + _scale, re.IGNORECASE),
            re.compile(
                r'\b(?:salary|pay|compensation)\s*[:\s]+EGP\s+\d[\d,،]*'
                + _scale, re.IGNORECASE),
        ]

        # Salary RANGE patterns — indicate a salary band/range, not an exact personal salary.
        # These are C2 (not C3): the document discloses a range but not the individual's
        # specific figure. E.g. employment offer letters, HR job postings, salary certificates
        # that show a band rather than a precise amount.
        # Pattern: "EGP X – EGP Y", "EGP X to EGP Y", "salary range", "salary band", "pay band"
        self.salary_range_patterns = [
            # "EGP 18,000 – EGP 22,000" or "EGP 18000 to EGP 22000" (dash, em-dash, en-dash, or "to")
            re.compile(
                r'EGP\s+\d[\d,،]*\s*(?:[-\u2013\u2014]|\bto\b)\s*EGP\s+\d[\d,،]*'
                + _scale, re.IGNORECASE),
            # "18,000 – 22,000 EGP" or "18000 to 22000 EGP"
            re.compile(
                r'\d[\d,،]*\s*(?:[-\u2013\u2014]|\bto\b)\s*\d[\d,،]*\s*EGP'
                + _scale, re.IGNORECASE),
            # "salary range", "salary band", "pay band", "pay range", "wage band"
            re.compile(
                r'\b(?:salary|pay|wage|compensation)\s+(?:range|band)\b',
                re.IGNORECASE),
            re.compile(
                r'\brange\s+(?:of\s+)?(?:salary|pay|compensation)\b',
                re.IGNORECASE),
            # Arabic: "نطاق الراتب", "بند الراتب", "حزمة الراتب"
            re.compile(r'\b(?:نطاق|نطاق الراتب|حزمة الراتب)\b'),
        ]

        # Personal data patterns
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'\b(?:01[0125]\d{8}|02\d{7,8})\b')

        # Account number — Egyptian bank account numbers (10-16 digits)
        self.account_number_pattern = re.compile(r'\b\d{10,16}\b')

        # Labeled account number — requires "Account Number" / "رقم الحساب" label
        # nearby. Used in classify_by_rules() as a C3 trigger.
        # Bare digit sequences (without a label) are excluded to avoid false positives
        # on phone numbers, product codes, and amounts in financial reports.
        self.labeled_account_pattern = re.compile(
            r'\b(?:account\s*(?:number|no\.?|#)|رقم\s*الحساب|رقم\s*حساب)'
            r'\s*[:\s]*\d{6,16}\b',
            re.IGNORECASE
        )

        # Date of birth patterns
        self.dob_pattern = re.compile(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\b')

        # Extended mobile: Egyptian numbers
        self.mobile_pattern = re.compile(r'\b01[0125]\d{8}\b')

        # Credit/debit card number
        self.card_pattern = re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b')

        # Risk rating — text pattern (English and Arabic)
        self.risk_pattern = re.compile(
            r'\b(high risk|medium risk|low risk)\b|'
            r'\bRisk\s*(?:Level|Rating|Classification)\s*[:\-]?\s*(High|Medium|Low)\b|'
            r'\b(مرتفعة|متوسطة|منخفضة)\b.*?\bالمخاطر\b|'
            r'\bمستوى\s*المخاطر\s*[:\-]?\s*(مرتفع|متوسط|منخفض)\b',
            re.IGNORECASE | re.DOTALL
        )

        # Sanctions screening result
        self.sanctions_pattern = re.compile(
            r'\b(world.?check|sanctions.?check|sanctions.?screening|'
            r'automated.?sanctions|قائمة.?العقوبات|فحص.?العقوبات)\b',
            re.IGNORECASE
        )

        # Source of funds
        self.source_of_funds_pattern = re.compile(
            r'\b(source.?of.?funds|مصدر.?الأموال|مصادر.?الدخل|'
            r'source.?of.?income|مصدر.?الدخل)\b',
            re.IGNORECASE
        )

        # RIM number (bank customer reference)
        self.rim_pattern = re.compile(r'\bRIM\s*[Nn]umber\b|\bRIM\s*[:#]\s*\d+\b', re.IGNORECASE)

        # Purpose of account
        self.purpose_pattern = re.compile(
            r'\b(purpose.?of.?account|الغرض.?من.?فتح.?الحساب|'
            r'use.?of.?account|استخدام.?الحساب)\b',
            re.IGNORECASE
        )

        # KYC / AML indicators
        self.kyc_pattern = re.compile(
            r'\b(KYC|know.?your.?customer|due.?diligence|'
            r'AML|anti.?money.?launder|PEP|politically.?exposed|'
            r'فتح.?حساب|اتفاقية)\b',
            re.IGNORECASE
        )

        # Special nature customer / PEP flag
        self.pep_pattern = re.compile(
            r'\b(special.?nature|politically.?exposed|PEP|'
            r'عميل.?خاص|شخصية.?سياسية)\b',
            re.IGNORECASE
        )

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
            # Investor relations / publicly published financial reports
            'investor relations', 'annual report', 'quarterly results',
            'earnings per share', 'financial highlights', 'financial results',
            'capital adequacy ratio', 'net interest margin', 'return on equity',
            'non-performing loans', 'npl ratio', 'earnings release',
            'علاقات المستثمرين', 'نتائج مالية', 'التقرير السنوي',
            'ربحية السهم', 'كفاية رأس المال',
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
        # NOTE: 'due diligence' removed — appears in governance/ethics docs as general obligation
        # NOTE: 'strategic plan' removed — appears in publicly published governance manuals
        self.confidential_keywords = [
            'budget allocation', 'budget proposal', 'budget approval',
            'roi analysis', 'return on investment',
            'transformation strategy',
            'cost reduction plan', 'revenue projection', 'financial projection',
            'proprietary', 'not for distribution', 'do not share',
            'competitive analysis', 'market strategy', 'pricing strategy',
            'merger', 'acquisition',
            'board confidential', 'executive only',
        ]

        # Public governance/institutional document signals — indicates a publicly published
        # governance, ethics, or regulatory document whose contact info is organizational,
        # not personal data under PDPL
        self.governance_signals = [
            'code of ethics', 'corporate governance', 'governance framework',
            'governance manual', 'governance code', 'governance report',
            'كود الحوكمة', 'دليل الحوكمة', 'قواعد الحوكمة', 'تقرير الحوكمة',
            'consumer protection', 'customer protection policy',
            'complaints policy', 'customer charter',
            'regulatory framework', 'compliance framework',
            'national bank of egypt', 'central bank of egypt',
            'annual report', 'sustainability report',
            # Investor relations / publicly published financial reports
            'investor relations', 'quarterly results', 'quarterly earnings',
            'earnings release', 'financial results', 'financial highlights',
            'earnings per share', 'return on equity', 'net interest margin',
            'non-performing loans', 'npl ratio', 'capital adequacy',
            'basel', 'tier 1 capital', 'risk-weighted assets',
            'نتائج مالية', 'علاقات المستثمرين', 'تقرير ربع سنوي',
            'ربحية السهم', 'كفاية رأس المال',
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

    def detect_credit_card(self, text: str) -> bool:
        """Check if text contains a credit/debit card number (16 digits in groups of 4)"""
        return bool(self.card_pattern.search(text))

    def detect_labeled_account_number(self, text: str) -> bool:
        """Check if text contains a labeled bank account number.
        Requires the label 'Account Number' / 'رقم الحساب' to appear near digits,
        to avoid false-positives on raw amounts, phone numbers, or product codes."""
        return bool(self.labeled_account_pattern.search(text))

    def detect_salary(self, text: str) -> bool:
        """Check if text contains salary information (EGP, USD, or generic formats)"""
        return any(pattern.search(text) for pattern in self.salary_patterns)

    def detect_salary_range(self, text: str) -> bool:
        """Check if text contains a salary RANGE/BAND (C2, not C3).
        A salary range shows a band (e.g. EGP 18,000–22,000) rather than an exact
        individual figure — sensitive enough for C2 but not C3."""
        return any(pattern.search(text) for pattern in self.salary_range_patterns)
    
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
    
    def check_c3_triggers(self, text: str) -> dict:
        """
        Check all CDE (Critical Data Element) patterns and return a dict of detected triggers.
        Returns:
            {
                "national_id": bool,
                "iban": bool,
                "account_number": bool,
                "salary": bool,
                "risk_rating": bool,
                "sanctions_check": bool,
                "source_of_funds": bool,
                "pep_flag": bool,
                "passport": bool,
                "card_number": bool,
                "kyc_indicator": bool,
                "date_of_birth": bool,
                "mobile": bool,
                "rim_number": bool,
            }
        """
        # account_number: only flag if not already captured by national_id (14 digits)
        # avoid double-counting 14-digit national IDs as account numbers
        has_account = bool(self.account_number_pattern.search(text)) and not self.detect_national_id(text)

        return {
            "national_id":    self.detect_national_id(text),
            "iban":           self.detect_iban(text),
            "account_number": has_account,
            "salary":         self.detect_salary(text),
            "risk_rating":    bool(self.risk_pattern.search(text)),
            "sanctions_check": bool(self.sanctions_pattern.search(text)),
            "source_of_funds": bool(self.source_of_funds_pattern.search(text)),
            "pep_flag":       bool(self.pep_pattern.search(text)),
            "passport":       self.detect_passport(text),
            "card_number":    bool(self.card_pattern.search(text)),
            "kyc_indicator":  bool(self.kyc_pattern.search(text)),
            "date_of_birth":  bool(self.dob_pattern.search(text)),
            "mobile":         bool(self.mobile_pattern.search(text)),
            "rim_number":     bool(self.rim_pattern.search(text)),
        }

    def identify_document_type(self, text: str) -> dict:
        """
        Identify the banking process, stage, and document type from text content.
        Returns:
            {
                "process": str,
                "stage": str,
                "document_type": str,
                "confidence": float
            }
        """
        tl = text.lower()

        # Score each doc type with keyword matches
        def score(keywords):
            return sum(1 for kw in keywords if kw in tl)

        scores = {
            "Account Opening Agreement": score([
                "account opening", "فتح حساب", "rim number", "rim:", "account classification",
                "account type", "purpose of account", "الغرض من فتح الحساب",
                "current account", "savings account", "investment account",
                "اتفاقية فتح", "banking services agreement",
            ]),
            "KYC Form": score([
                "know your customer", "kyc", "due diligence", "world check",
                "sanctions", "sanctions screening", "automated sanctions",
                "source of funds", "pep", "politically exposed", "risk level",
                "فحص العقوبات", "مصدر الأموال",
            ]),
            "Salary Certificate": score([
                "salary certificate", "شهادة راتب", "net monthly salary",
                "الراتب الشهري", "to whom it may concern", "إلى من يهمه الأمر",
            ]),
            "Payroll Report": score([
                "payroll", "كشف رواتب", "payroll report", "department payroll",
                "monthly payroll", "net salary", "deductions", "allowances",
            ]),
            "Loan Application": score([
                "loan application", "طلب قرض", "personal loan", "credit",
                "financing", "loan amount", "tenor", "repayment",
            ]),
            "Bank Statement": score([
                "statement of account", "bank statement", "كشف حساب",
                "opening balance", "closing balance", "transactions",
            ]),
            "Employment Contract": score([
                "employment contract", "عقد عمل", "عقد توظيف",
                "terms of employment", "probation period",
            ]),
            "Vendor Contract": score([
                "vendor", "supplier", "service agreement", "service provider",
                "contract", "deliverables", "payment terms", "sla",
            ]),
            "Internal Memo": score([
                "memo", "memorandum", "مذكرة", "from:", "to:", "subject:",
                "all staff", "جميع الموظفين",
            ]),
            "Meeting Minutes": score([
                "meeting minutes", "minutes of meeting", "محضر اجتماع",
                "attendees", "agenda", "action items", "committee",
            ]),
            "Performance Improvement Plan": score([
                "performance improvement", "pip", "improvement objectives",
                "review date", "improvement plan",
            ]),
            "Warning Letter": score([
                "warning letter", "formal notice", "disciplinary", "misconduct",
                "below standard", "performance notice",
            ]),
            "Credit Assessment": score([
                "credit assessment", "credit score", "debt-to-income",
                "credit limit", "assessment outcome",
            ]),
            "Background Check": score([
                "background check", "onboarding form", "background verification",
                "criminal conviction", "education certificates",
            ]),
        }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score == 0:
            best_type = "General Banking Document"
            confidence = 0.3
        elif best_score == 1:
            confidence = 0.55
        elif best_score == 2:
            confidence = 0.70
        elif best_score == 3:
            confidence = 0.82
        else:
            confidence = min(0.95, 0.82 + (best_score - 3) * 0.04)

        # Map document type → process + stage
        process_map = {
            "Account Opening Agreement": ("Account Opening", "Customer Identification"),
            "KYC Form": ("Account Opening", "Risk Assessment"),
            "Salary Certificate": ("Back Office", "Internal Operations"),
            "Payroll Report": ("Back Office", "Internal Operations"),
            "Loan Application": ("Loan Processing", "Customer Identification"),
            "Bank Statement": ("Customer Service", "Ongoing Relationship"),
            "Employment Contract": ("Back Office", "Account Setup"),
            "Vendor Contract": ("Back Office", "Account Setup"),
            "Internal Memo": ("Back Office", "Internal Operations"),
            "Meeting Minutes": ("Back Office", "Internal Operations"),
            "Performance Improvement Plan": ("Back Office", "Internal Operations"),
            "Warning Letter": ("Back Office", "Internal Operations"),
            "Credit Assessment": ("Loan Processing", "Risk Assessment"),
            "Background Check": ("Back Office", "Customer Identification"),
            "General Banking Document": ("Unknown", "Unknown"),
        }

        process, stage = process_map.get(best_type, ("Unknown", "Unknown"))
        return {
            "process": process,
            "stage": stage,
            "document_type": best_type,
            "confidence": round(confidence, 2),
        }

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

        # Early governance/public-document detection.
        # Annual reports, investor relations, consumer protection publications,
        # and governance manuals often contain 16-digit codes in tables and
        # aggregate financial figures that match C3 patterns but are NOT real
        # personal data. Suppress these soft false-positives for such documents.
        # (Hard PII — National ID, IBAN, Passport, labeled Account Number — is
        # always checked: it is unambiguous and should not appear in public docs.)
        _text_lower_pre = text.lower()
        _is_governance = any(sig in _text_lower_pre for sig in self.governance_signals)

        # Check C3 triggers (PII and financial data)
        if self.detect_national_id(text):
            triggers.append('National ID')

        if self.detect_passport(text):
            triggers.append('Passport')

        if self.detect_iban(text):
            triggers.append('IBAN')

        if self.detect_labeled_account_number(text):
            triggers.append('Account Number')

        # Credit card: suppressed for governance/public documents — 16-digit codes in
        # product tables, regulatory reference numbers, and financial data matrices
        # frequently match the card pattern but are not actual payment card numbers.
        if not _is_governance and self.detect_credit_card(text):
            triggers.append('Credit Card')

        # Salary: suppressed for governance/public documents — aggregate per-share or
        # per-unit financial figures can match salary patterns in annual reports.
        # Also suppressed for individual job offer / promotion letters — these are
        # one-to-one documents (C2), not mass-exposure records (C3), even when they
        # contain an exact salary figure. Systemic risk requires bulk exposure.
        _job_offer_signals = [
            'job offer', 'offer of employment', 'letter of appointment',
            'appointment letter', 'offer letter', 'promotion letter',
            'employment offer', 'we are pleased to offer',
            'pleased to confirm your appointment', 'pleased to inform you',
            'we are delighted to offer', 'congratulations on your promotion',
            'your appointment as', 'your promotion to',
            'خطاب عرض', 'عرض وظيفة', 'خطاب تعيين', 'خطاب ترقية',
            'يسعدنا إبلاغك', 'نود إبلاغك بترقيتك',
        ]
        _is_offer_letter = any(sig in _text_lower_pre for sig in _job_offer_signals)
        if not _is_governance and not _is_offer_letter and self.detect_salary(text):
            triggers.append('Salary')

        if triggers:
            return {
                'classification': 'C3',
                'confidence': None,  # AI determines confidence
                'triggers': triggers,
                'reasoning': f"Contains: {', '.join(triggers)}"
            }

        # Job offer / promotion letter with exact salary → C2
        # (individual employment record; one-to-one communication, not systemic risk)
        if _is_offer_letter and self.detect_salary(text):
            return {
                'classification': 'C2',
                'confidence': None,
                'triggers': ['Salary (Offer/Promotion Letter)'],
                'reasoning': 'Individual employment offer or promotion letter with salary — C2 (one-to-one record, not systemic risk)'
            }

        # Check for salary RANGE — C2 or C3 depending on document type
        # Salary range/band → C2 (individual employment data, not systemic risk)
        # Job offer letters and promotion letters with a salary range are C2:
        # one-to-one records that are sensitive but not systemically dangerous.
        if self.detect_salary_range(text):
            return {
                'classification': 'C2',
                'confidence': None,
                'triggers': ['Salary Range'],
                'reasoning': 'Contains salary range/band — individual employment data (C2)'
            }

        text_lower = text.lower()

        # Check for CV/Resume - these are always C2 (Personal Data)
        # Only unambiguous CV-specific phrases — generic words like 'experience',
        # 'education', 'skills', 'cv' are excluded because they appear in annual
        # reports, policy papers, and other public documents.
        cv_indicators = [
            'curriculum vitae', 'work history', 'employment history',
            'professional summary', 'career objective', 'references available',
            'السيرة الذاتية', 'الخبرات المهنية', 'المؤهلات الدراسية',
        ]
        # Negative override: documents that are clearly institutional/public reports
        annual_report_signals = [
            'annual report', 'fiscal year', 'world bank', 'imf ', 'international monetary',
            'balance sheet', 'total assets', 'net income', 'shareholders', 'press release',
            'central bank', 'ministry of', 'government of', 'united nations',
        ]
        is_institutional = any(sig in text_lower for sig in annual_report_signals)

        cv_score = sum(1 for indicator in cv_indicators if indicator in text_lower)
        has_email, has_phone = self.detect_personal_data(text)

        # If it looks like a CV (1+ strong indicator) and has contact info, it's C2
        # but never fire on institutional/public reports
        if cv_score >= 1 and (has_email or has_phone) and not is_institutional:
            triggers.append('CV/Resume')
            return {
                'classification': 'C2',
                'confidence': None,
                'triggers': triggers,
                'reasoning': f'CV/Resume with personal contact information ({cv_score} CV indicators)'
            }

        # Governance/public document fast-path: return C0 directly.
        # Annual reports, investor relations, consumer protection publications,
        # and governance manuals are intended for public audiences. Generic
        # internal keywords ('operations', 'internal', 'team') appear in their
        # prose but do NOT make the document staff-only. Trust the governance
        # signal over internal keyword count. Hard C3 PII (checked above) and
        # salary range / CV (checked above) still take precedence when present.
        if _is_governance:
            return {
                'classification': 'C0',
                'confidence': None,
                'triggers': ['Governance/Public document'],
                'reasoning': 'Publicly published governance or institutional document — C0'
            }

        # Check for internal keywords FIRST (training, meetings, etc.)
        internal_count = sum(1 for kw in self.internal_keywords
                           if kw.lower() in text_lower)
        is_internal_document = internal_count >= 1

        # Check for public keywords
        public_count = sum(1 for kw in self.public_keywords
                         if kw.lower() in text_lower)
        is_public_document = public_count >= 1 or 'press release' in text_lower or 'press@' in text_lower

        # Detect publicly published governance/institutional documents.
        # These list organizational contact info (board members, official emails)
        # which is NOT personal data under PDPL — skip Personal Data escalation.
        is_governance_doc = any(sig in text_lower for sig in self.governance_signals)

        # Check for contract/agreement keywords (includes banking agreements).
        # NOTE: bare 'contract' is intentionally excluded — it appears in annual reports,
        # governance manuals, and investor relations documents as a general concept
        # ("contractual obligations", "service contract with regulators") and would
        # falsely trigger the Personal Data check via has_contract_keywords.
        has_contract_keywords = any(kw in text_lower for kw in
                                   ['employment agreement', 'employment contract',
                                    'account opening agreement', 'banking services agreement',
                                    'اتفاقية فتح حساب', 'إتفاقية فتح حساب',
                                    'عقد عمل', 'عقد توظيف'])

        # Check C2 triggers.
        # Skip entirely for governance/institutional/public documents — their contact
        # info (IR email, board member phone) is organizational, not personal PDPL data.
        # Enter for: specific contract docs (employment/account opening), OR documents
        # that are neither clearly internal nor clearly public.
        if (has_contract_keywords and not is_governance_doc) or \
                (not is_internal_document and not is_public_document and not is_governance_doc):
            has_email, has_phone = self.detect_personal_data(text)
            # More specific name pattern - exclude common title words
            name_matches = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text)
            # Filter out common non-name patterns
            non_names = {
                'Risk Management', 'Training Announcement', 'Human Resources',
                'Customer Service', 'Bank Misr', 'Annual Report', 'Service Update',
                # Common banking / financial report capitalized phrases
                'National Bank', 'Central Bank', 'Egyptian Exchange', 'Stock Exchange',
                'Capital Markets', 'Financial Markets', 'Investment Bank', 'Commercial Bank',
                'Board Directors', 'Managing Director', 'Chief Executive', 'Deputy Governor',
                'Financial Results', 'Quarterly Results', 'Financial Highlights',
                'Net Income', 'Total Assets', 'Total Equity', 'Return Equity',
                'Capital Adequacy', 'Risk Weighted', 'Non Performing', 'Net Interest',
                'Investor Relations', 'Financial Statements', 'Financial Report',
                'December Results', 'September Results', 'June Results', 'March Results',
                'Egyptian Pounds', 'United Arab', 'Saudi Arabia', 'Cairo Egypt',
                'Basel Committee', 'International Monetary', 'World Bank',
            }
            actual_names = [m for m in name_matches if m not in non_names]
            has_name = len(actual_names) > 0

            # Check for filled account/reference numbers (indicates a filled form, not blank)
            has_account_number = bool(re.search(r'\b\d{6,10}\b', text))

            # C2 if: (contract + contact) OR (name + contact in non-internal, non-governance doc)
            # OR (banking agreement + filled customer name + account number)
            # Governance/institutional docs are excluded: their contact info is organizational,
            # not personal data under PDPL (e.g. board member email in a public Code of Ethics)
            if (has_contract_keywords and (has_email or has_phone)) or \
               (not is_internal_document and not is_governance_doc and has_name and (has_email or has_phone)) or \
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