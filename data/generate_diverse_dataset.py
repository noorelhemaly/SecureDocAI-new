#!/usr/bin/env python3
"""
Diverse Test Dataset Generator for Egyptian Banking Document Classification
Generates mixed Arabic/English documents with valid Egyptian PII formats

NO CLASSIFICATION KEYWORDS - classifier must understand content, not keywords

Author: Noor Elhemaly (202300013)
"""

import json
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict

# =============================================================================
# VALID EGYPTIAN DATA GENERATORS
# =============================================================================

def generate_national_id() -> str:
    """
    Generate valid 14-digit Egyptian National ID
    Format: [century][YY][MM][DD][governorate][sequence][check]
    """
    century = random.choice(['2', '3'])
    year = f"{random.randint(0, 99):02d}"
    month = f"{random.randint(1, 12):02d}"
    day = f"{random.randint(1, 28):02d}"
    governorate = f"{random.randint(1, 35):02d}"
    sequence = f"{random.randint(0, 9999):04d}"
    check = str(random.randint(0, 9))
    return f"{century}{year}{month}{day}{governorate}{sequence}{check}"


def generate_passport() -> str:
    """Generate Egyptian passport number (Letter + 7-8 digits)"""
    letter = random.choice(['A', 'B', 'C', 'D'])
    digits = ''.join([str(random.randint(0, 9)) for _ in range(random.randint(7, 8))])
    return f"{letter}{digits}"


def generate_iban() -> str:
    """Generate valid Egyptian IBAN (EG + 27 digits)"""
    return f"EG{''.join([str(random.randint(0, 9)) for _ in range(27)])}"


def generate_phone() -> str:
    """Generate Egyptian mobile number"""
    prefix = random.choice(['010', '011', '012', '015'])
    return f"{prefix}{''.join([str(random.randint(0, 9)) for _ in range(8)])}"


def generate_salary_egp() -> tuple:
    """Generate salary in EGP with Arabic and English formats"""
    amount = random.randint(8000, 150000)
    formats = [
        f"{amount:,} EGP",
        f"{amount} جنيه مصري",
        f"{amount:,} ج.م",
        f"EGP {amount:,}",
    ]
    return amount, random.choice(formats)


def generate_salary_usd() -> tuple:
    """Generate salary in USD"""
    amount = random.randint(1000, 50000)
    formats = [
        f"${amount:,}",
        f"${amount // 1000}K" if amount >= 1000 else f"${amount}",
        f"{amount:,} USD",
        f"USD {amount:,}",
    ]
    return amount, random.choice(formats)


# =============================================================================
# NAME GENERATORS
# =============================================================================

ARABIC_FIRST_NAMES = [
    "أحمد", "محمد", "علي", "عمر", "يوسف", "خالد", "طارق", "حسن", "إبراهيم", "مصطفى",
    "فاطمة", "مريم", "نور", "سارة", "هدى", "رنا", "دينا", "منى", "ليلى", "ياسمين",
    "عبدالله", "عبدالرحمن", "كريم", "شريف", "وليد", "هشام", "سامي", "رامي", "باسم", "تامر"
]

ARABIC_LAST_NAMES = [
    "محمود", "إبراهيم", "حسين", "علي", "أحمد", "السيد", "عبدالله", "الشريف", "المصري", "النجار",
    "الفقي", "سالم", "عثمان", "حسن", "خليل", "منصور", "رشدي", "فهمي", "زكي", "نصر"
]

ENGLISH_FIRST_NAMES = [
    "Ahmed", "Mohamed", "Ali", "Omar", "Youssef", "Khaled", "Tarek", "Hassan", "Ibrahim", "Mostafa",
    "Fatma", "Mariam", "Nour", "Sarah", "Hoda", "Rana", "Dina", "Mona", "Laila", "Yasmine",
    "Abdullah", "Abdelrahman", "Karim", "Sherif", "Walid", "Hesham", "Sami", "Ramy", "Bassem", "Tamer"
]

ENGLISH_LAST_NAMES = [
    "Mahmoud", "Ibrahim", "Hussein", "Ali", "Ahmed", "ElSayed", "Abdullah", "ElSherif", "ElMasry", "ElNaggar",
    "ElFeky", "Salem", "Osman", "Hassan", "Khalil", "Mansour", "Roshdy", "Fahmy", "Zaki", "Nasr"
]


def generate_name(language: str = "mixed") -> tuple:
    """
    Generate name in specified language
    Returns (full_name, first_name, last_name, email_name)
    email_name is always Latin characters for valid email addresses
    """
    # Pick index for consistent Arabic/English pairing
    idx = random.randint(0, len(ENGLISH_FIRST_NAMES) - 1)
    last_idx = random.randint(0, len(ENGLISH_LAST_NAMES) - 1)

    if language == "arabic":
        first = ARABIC_FIRST_NAMES[idx % len(ARABIC_FIRST_NAMES)]
        last = ARABIC_LAST_NAMES[last_idx % len(ARABIC_LAST_NAMES)]
    elif language == "english":
        first = ENGLISH_FIRST_NAMES[idx]
        last = ENGLISH_LAST_NAMES[last_idx]
    else:  # mixed
        if random.random() > 0.5:
            first = ARABIC_FIRST_NAMES[idx % len(ARABIC_FIRST_NAMES)]
            last = ARABIC_LAST_NAMES[last_idx % len(ARABIC_LAST_NAMES)]
        else:
            first = ENGLISH_FIRST_NAMES[idx]
            last = ENGLISH_LAST_NAMES[last_idx]

    # Email always uses English names (emails can't be in Arabic)
    email_first = ENGLISH_FIRST_NAMES[idx].lower()
    email_last = ENGLISH_LAST_NAMES[last_idx].lower()
    email_name = f"{email_first}.{email_last}"

    return f"{first} {last}", first, last, email_name


# =============================================================================
# DEPARTMENT & POSITION DATA
# =============================================================================

DEPARTMENTS_EN = ["Finance", "HR", "IT", "Operations", "Legal", "Marketing", "Risk Management", "Compliance"]
DEPARTMENTS_AR = ["المالية", "الموارد البشرية", "تكنولوجيا المعلومات", "العمليات", "الشؤون القانونية", "التسويق", "إدارة المخاطر", "الالتزام"]

POSITIONS_EN = ["Manager", "Senior Analyst", "Officer", "Specialist", "Director", "Team Lead", "Coordinator", "Executive"]
POSITIONS_AR = ["مدير", "محلل أول", "موظف", "أخصائي", "مدير تنفيذي", "قائد فريق", "منسق", "تنفيذي"]


# =============================================================================
# C0 - PUBLIC DOCUMENTS (no sensitive data)
# =============================================================================

def generate_c0_document() -> Dict:
    """Generate C0 (Public) document - publicly available information"""
    templates = [
        # English press release
        lambda: {
            "text": f"""Bank Misr - بنك مصر
{datetime.now().strftime('%B %Y')}

{random.choice([
    'We are pleased to announce our new digital banking services available to all customers.',
    'Bank Misr expands branch network with new locations in Upper Egypt governorates.',
    'Our partnership with leading fintech companies brings innovative solutions.',
    'Bank Misr receives regional excellence award for customer satisfaction.',
    'New sustainable banking initiative launches across all branches.'
])}

{random.choice([
    'يسعدنا الإعلان عن خدماتنا المصرفية الرقمية الجديدة.',
    'بنك مصر يوسع شبكة فروعه في محافظات الصعيد.',
    'شراكتنا مع شركات التكنولوجيا المالية تقدم حلولاً مبتكرة.'
])}

Media: press@bankmisr.com
www.bankmisr.com""",
            "format": "press_release"
        },
        # Holiday announcement
        lambda: {
            "text": f"""إعلان - Announcement

Bank Misr branches will be closed on {random.choice(['Thursday', 'Friday', 'Saturday'])} for {random.choice(['Eid Al-Fitr', 'Eid Al-Adha', 'National Day', 'Revolution Day', '6th October'])}.

ستكون فروع بنك مصر مغلقة يوم {random.choice(['الخميس', 'الجمعة', 'السبت'])} بمناسبة {random.choice(['عيد الفطر', 'عيد الأضحى', 'اليوم الوطني', 'ذكرى الثورة'])}.

Online banking: متاح 24/7
ATM services: operational
خدمات الصراف الآلي: متاحة""",
            "format": "holiday_announcement"
        },
        # Job posting
        lambda: {
            "text": f"""فرصة عمل - Career Opportunity

Position المنصب: {random.choice(POSITIONS_EN)}
Department القسم: {random.choice(DEPARTMENTS_EN)}
Location الموقع: {random.choice(['Cairo القاهرة', 'Alexandria الإسكندرية', 'Giza الجيزة'])}

Requirements المتطلبات:
- Bachelor's degree in relevant field درجة البكالوريوس
- {random.randint(2, 8)} years of experience سنوات خبرة
- Fluent in Arabic and English إجادة العربية والإنجليزية
- Strong communication skills مهارات تواصل قوية

Benefits المزايا:
- Competitive package حزمة تنافسية
- Medical insurance تأمين طبي
- Training programs برامج تدريبية

Apply قدم الآن: careers@bankmisr.com
Deadline الموعد النهائي: {(datetime.now() + timedelta(days=random.randint(14, 30))).strftime('%Y-%m-%d')}""",
            "format": "job_posting"
        },
        # Service update
        lambda: {
            "text": f"""تحديث الخدمات - Service Update

{random.choice([
    'Mobile app version 4.0 is now available with enhanced features.',
    'Online transfer limits have been increased for premium customers.',
    'New ATM locations added in major shopping centers.',
    'Customer service hours extended to 10 PM daily.'
])}

{random.choice([
    'تطبيق الهاتف الإصدار 4.0 متاح الآن مع مميزات محسنة.',
    'تم زيادة حدود التحويل عبر الإنترنت لعملاء البريميوم.',
    'تمت إضافة مواقع صراف آلي جديدة في المراكز التجارية الكبرى.',
    'تم تمديد ساعات خدمة العملاء حتى الساعة 10 مساءً.'
])}

Details التفاصيل: www.bankmisr.com/updates
Support الدعم: 19888""",
            "format": "service_update"
        },
        # Branch information
        lambda: {
            "text": f"""معلومات الفرع - Branch Information

{random.choice(['Maadi', 'Heliopolis', 'Dokki', 'Nasr City', 'Mohandessin'])} Branch
فرع {random.choice(['المعادي', 'مصر الجديدة', 'الدقي', 'مدينة نصر', 'المهندسين'])}

Working Hours ساعات العمل:
Sunday-Thursday الأحد-الخميس: 8:30 AM - 3:00 PM
Friday-Saturday الجمعة-السبت: Closed مغلق

Services الخدمات:
- Deposits and withdrawals الإيداع والسحب
- Account opening فتح حسابات
- Foreign exchange صرف العملات
- Bill payments دفع الفواتير

Location الموقع: {random.randint(1, 200)} {random.choice(['Tahrir St', 'Ramses St', 'Pyramids Rd'])}
Hotline الخط الساخن: 19888""",
            "format": "branch_info"
        },
    ]

    doc = random.choice(templates)()
    return {
        "text": doc["text"],
        "classification": "C0",
        "format": doc["format"]
    }


# =============================================================================
# C1 - INTERNAL DOCUMENTS (operational, no personal data)
# =============================================================================

def generate_c1_document() -> Dict:
    """Generate C1 (Internal) document - internal operational information"""
    dept_en = random.choice(DEPARTMENTS_EN)
    dept_ar = DEPARTMENTS_AR[DEPARTMENTS_EN.index(dept_en)]
    date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d')

    templates = [
        # Meeting minutes
        lambda: {
            "text": f"""محضر اجتماع - Meeting Minutes

القسم Department: {dept_ar} / {dept_en}
التاريخ Date: {date}
الوقت Time: {random.randint(9, 16)}:00

الحضور Attendees:
- رئيس القسم Department Head
- أعضاء الفريق Team Members ({random.randint(4, 12)} persons)

جدول الأعمال Agenda:
1. {random.choice(['مراجعة الربع الرابع Q4 Review', 'تحديثات المشروع Project Updates', 'تحسين العمليات Process Improvement'])}
2. {random.choice(['مناقشة الميزانية Budget Discussion', 'مراجعة الجدول الزمني Timeline Review', 'تخطيط الموارد Resource Planning'])}
3. {random.choice(['جدول التدريب Training Schedule', 'توزيع المهام Task Allocation'])}

القرارات Decisions:
- {random.choice(['الموافقة على الخطة المقترحة', 'تأجيل القرار للاجتماع القادم', 'تشكيل لجنة فرعية للدراسة'])}

المهام Action Items:
- تحديث الإجراءات Update procedures - Due: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}
- جدولة المتابعة Schedule follow-up

الاجتماع القادم Next meeting: {(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')}""",
            "format": "meeting_minutes"
        },
        # Internal memo
        lambda: {
            "text": f"""مذكرة - Memo

من From: رئيس قسم {dept_ar}
إلى To: جميع موظفي القسم All {dept_en} Staff
التاريخ Date: {date}
الموضوع Subject: {random.choice(['تحديث ساعات العمل', 'إجراءات جديدة', 'إعادة هيكلة الفريق', 'إعلان تدريب'])}

{random.choice([
    'سيتم تطبيق ساعات عمل جديدة اعتباراً من الأسبوع القادم. يرجى مراجعة الجدول المرفق.',
    'جميع أعضاء الفريق مطالبون بحضور جلسة التدريب القادمة المقررة يوم الأحد.',
    'سيخضع القسم لإعادة هيكلة لتحسين الكفاءة. سيتم الإعلان عن التفاصيل قريباً.',
    'إجراءات الموافقة الجديدة ستكون سارية المفعول فوراً. يرجى مراجعة الدليل المحدث.'
])}

{random.choice([
    'New working hours will be implemented starting next week.',
    'All team members are required to attend the upcoming training session.',
    'The department will undergo restructuring to improve efficiency.',
    'New approval procedures will be effective immediately.'
])}

للاستفسارات For questions: {dept_en.lower()}@bankmisr.com""",
            "format": "memo"
        },
        # Project status report
        lambda: {
            "text": f"""تقرير حالة المشروع - Project Status

المشروع Project: {random.choice(['التحول الرقمي Digital Transformation', 'ترقية النظام المصرفي Core Banking Upgrade', 'بوابة العملاء Customer Portal', 'تطبيق الهاتف v2.0 Mobile App'])}
القسم Department: {dept_en}
التاريخ Date: {date}
الحالة Status: {random.choice(['على المسار On Track', 'متأخر Delayed', 'متقدم Ahead of Schedule'])}

التقدم Progress:
- المرحلة 1 Phase 1: مكتمل 100% Completed
- المرحلة 2 Phase 2: {random.choice(['قيد التنفيذ In Progress', 'معلق Pending', 'مكتمل 75%'])}
- المرحلة 3 Phase 3: لم يبدأ Not Started

المخاطر Risks:
- {random.choice(['تأخر التسليم من الموردين', 'نقص الموارد البشرية', 'تغيير في المتطلبات'])}

المرحلة القادمة Next Milestone: {random.choice(['مرحلة الاختبار Testing', 'قبول المستخدم UAT', 'النشر Deployment'])}
الموعد المتوقع Expected: {(datetime.now() + timedelta(days=random.randint(14, 60))).strftime('%Y-%m-%d')}""",
            "format": "project_status"
        },
        # Policy document
        lambda: {
            "text": f"""سياسة - Policy Document

العنوان Title: {random.choice(['إرشادات العمل عن بعد Remote Work Guidelines', 'قواعد السلوك Code of Conduct', 'أمن المعلومات IT Security', 'سياسة الإجازات Leave Policy'])}
تاريخ السريان Effective: {date}
النطاق Scope: جميع موظفي {dept_ar} / All {dept_en} Employees
الإصدار Version: {random.randint(1, 5)}.0

الغرض Purpose:
تهدف هذه السياسة إلى تنظيم {random.choice(['العمليات اليومية', 'سلوك الموظفين', 'أمن المعلومات', 'ترتيبات العمل'])} في القسم.

This policy establishes guidelines for {random.choice(['daily operations', 'employee conduct', 'information security', 'work arrangements'])}.

الإجراءات Procedures:
1. {random.choice(['تقديم الطلب للمدير المباشر', 'الحصول على موافقة HR', 'إكمال النموذج المطلوب'])}
2. {random.choice(['انتظار الموافقة خلال 3 أيام عمل', 'تقديم المستندات المطلوبة', 'حضور جلسة التوجيه'])}

المسؤول Owner: {dept_en} Department
المراجعة القادمة Next Review: {(datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')}""",
            "format": "policy"
        },
        # Training announcement
        lambda: {
            "text": f"""إعلان تدريب - Training Announcement

البرنامج Program: {random.choice(['مهارات القيادة Leadership Skills', 'إدارة المشاريع Project Management', 'خدمة العملاء Customer Service', 'الأمن السيبراني Cybersecurity'])}
القسم Department: {dept_en}
التاريخ Date: {(datetime.now() + timedelta(days=random.randint(7, 30))).strftime('%Y-%m-%d')}
المدة Duration: {random.randint(1, 5)} days أيام
المكان Venue: {random.choice(['قاعة التدريب الرئيسية', 'عبر الإنترنت Online', 'مركز التدريب - المعادي'])}

المحتوى Content:
- {random.choice(['أساسيات الموضوع', 'تطبيقات عملية', 'دراسات حالة'])}
- {random.choice(['ورش عمل تفاعلية', 'تمارين جماعية', 'اختبار نهائي'])}

المستهدفون Target: {random.choice(['جميع الموظفين', 'المديرين', 'الموظفين الجدد', 'فريق IT'])}
التسجيل Registration: training@bankmisr.com
الموعد النهائي Deadline: {(datetime.now() + timedelta(days=random.randint(3, 14))).strftime('%Y-%m-%d')}""",
            "format": "training"
        },
    ]

    doc = random.choice(templates)()
    return {
        "text": doc["text"],
        "classification": "C1",
        "format": doc["format"]
    }


# =============================================================================
# C2 - CONFIDENTIAL (personal data, no financial/ID data)
# =============================================================================

def generate_c2_document() -> Dict:
    """Generate C2 document - contains personal contact data but no C3 triggers"""
    name_full, first, last, email_name = generate_name("mixed")
    phone = generate_phone()
    email = f"{email_name}@bankmisr.com"
    dept_en = random.choice(DEPARTMENTS_EN)
    dept_ar = DEPARTMENTS_AR[DEPARTMENTS_EN.index(dept_en)]
    position_en = random.choice(POSITIONS_EN)
    position_ar = POSITIONS_AR[POSITIONS_EN.index(position_en)]
    date = datetime.now().strftime('%Y-%m-%d')

    templates = [
        # Employment contract (no salary)
        lambda: {
            "text": f"""عقد توظيف - Employment Agreement

الموظف Employee: {name_full}
البريد الإلكتروني Email: {email}
الهاتف Phone: {phone}
المنصب Position: {position_ar} / {position_en}
القسم Department: {dept_ar} / {dept_en}
تاريخ البدء Start Date: {date}

الشروط والأحكام Terms:
- فترة الاختبار Probation: 3 months أشهر
- ساعات العمل Working hours: الأحد-الخميس Sunday-Thursday
- المزايا حسب سياسة الشركة Benefits as per company policy

مسؤوليات الوظيفة Job Responsibilities:
- {random.choice(['إدارة الفريق', 'تحليل البيانات', 'خدمة العملاء', 'تطوير الأنظمة'])}
- {random.choice(['إعداد التقارير', 'التنسيق مع الأقسام', 'متابعة المشاريع'])}

التوقيعات Signatures:
الموظف Employee: __________
الموارد البشرية HR: __________
التاريخ Date: {date}""",
            "format": "employment_contract"
        },
        # Performance review
        lambda: {
            "text": f"""تقييم الأداء - Performance Review

الموظف Employee: {name_full}
القسم Department: {dept_en}
المنصب Position: {position_en}
فترة التقييم Period: Q{random.randint(1, 4)} 2025

بيانات التواصل Contact:
{email}
{phone}

التقييمات Ratings:
المهارات التقنية Technical: {random.choice(['ممتاز Excellent', 'جيد جداً Very Good', 'جيد Good'])}
التواصل Communication: {random.choice(['ممتاز Excellent', 'جيد جداً Very Good', 'جيد Good'])}
العمل الجماعي Teamwork: {random.choice(['ممتاز Excellent', 'جيد جداً Very Good', 'جيد Good'])}
الالتزام بالمواعيد Punctuality: {random.choice(['ممتاز Excellent', 'جيد جداً Very Good', 'جيد Good'])}

الملاحظات Comments:
{random.choice([
    'يظهر مهارات تحليلية قوية وتفاني في العمل. Shows strong analytical skills and dedication.',
    'لاعب فريق ممتاز مع إمكانات قيادية. Excellent team player with leadership potential.',
    'يلتزم دائماً بالمواعيد النهائية ومعايير الجودة. Consistently meets deadlines and standards.',
    'يظهر مبادرة وقدرات حل المشكلات. Demonstrates initiative and problem-solving abilities.'
])}

المقيّم Reviewer: __________
التاريخ Date: {date}""",
            "format": "performance_review"
        },
        # Customer service record
        lambda: {
            "text": f"""سجل خدمة العملاء - Customer Service Record

العميل Client: {name_full}
الاتصال Contact: {phone}
البريد Email: {email}
التاريخ Date: {date}
الرقم المرجعي Ref: CSR-{random.randint(10000, 99999)}

نوع الاستفسار Inquiry: {random.choice(['طلب قرض Loan Application', 'فتح حساب Account Opening', 'خدمات البطاقات Card Services', 'استفسار عام General Inquiry'])}
الحالة Status: {random.choice(['قيد الانتظار Pending', 'قيد المعالجة In Progress', 'تم الحل Resolved'])}

تفاصيل Details:
{random.choice([
    'العميل استفسر عن أهلية القرض الشخصي ومتطلبات التقديم.',
    'طلب فتح حساب توفير جديد مع بطاقة خصم.',
    'استفسار عن حدود السحب اليومية وطلب زيادتها.',
    'شكوى بخصوص رسوم غير متوقعة على الحساب.'
])}

الإجراء المتخذ Action:
{random.choice([
    'تم تقديم المعلومات المطلوبة وإرسال النماذج عبر البريد.',
    'تم تحويل الطلب للقسم المختص للمراجعة.',
    'تم حل المشكلة وإخطار العميل بالنتيجة.',
    'مطلوب متابعة بعد مراجعة الطلب.'
])}

المتابعة Follow-up: {(datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')}
الموظف المسؤول Agent: {generate_name('english')[0]}""",
            "format": "customer_service"
        },
        # Vendor contact
        lambda: {
            "text": f"""اتفاقية مورد - Vendor Agreement

المورد Vendor: {random.choice(['Tech Solutions Ltd', 'Cairo Systems', 'Delta Services', 'Nile Tech', 'Smart Solutions'])}
المسؤول Contact: {name_full}
البريد Email: {email}
الهاتف Phone: {phone}

الخدمة Service: {random.choice(['دعم تقني IT Support', 'خدمات أمنية Security', 'استشارات Consulting', 'صيانة Maintenance'])}
مدة العقد Period: {random.randint(6, 24)} months شهر
القيمة Value: Subject to negotiation

الشروط Terms:
- اتفاقية مستوى الخدمة مرفقة SLA included
- مراجعة ربع سنوية Quarterly review
- إشعار إنهاء 30 يوم 30-day termination notice

جهة الاتصال بالبنك Bank Contact:
{generate_name('arabic')[0]}
{random.choice(DEPARTMENTS_EN)} Department
{generate_phone()}

تاريخ البدء Start: {date}
تاريخ الانتهاء End: {(datetime.now() + timedelta(days=random.randint(180, 730))).strftime('%Y-%m-%d')}""",
            "format": "vendor_agreement"
        },
        # Interview notes
        lambda: {
            "text": f"""ملاحظات المقابلة - Interview Notes

المرشح Candidate: {name_full}
الهاتف Phone: {phone}
البريد Email: {email}
المنصب Position: {position_en}
القسم Department: {dept_en}
تاريخ المقابلة Date: {date}

الخلفية Background:
- {random.randint(2, 15)} سنوات خبرة years experience
- {random.choice(['بكالوريوس', 'ماجستير'])} في {random.choice(['إدارة الأعمال', 'علوم الحاسب', 'المحاسبة', 'الهندسة'])}

التقييم Assessment:
المهارات التقنية Technical: {random.randint(3, 5)}/5
التواصل Communication: {random.randint(3, 5)}/5
الملاءمة الثقافية Cultural Fit: {random.randint(3, 5)}/5

الملاحظات Notes:
{random.choice([
    'مرشح قوي مع خبرة ذات صلة. يوصى بالتوظيف.',
    'مهارات جيدة لكن يحتاج مزيد من الخبرة في المجال.',
    'أداء ممتاز في المقابلة. مناسب للمنصب.',
    'يحتاج مقابلة ثانية مع مدير القسم.'
])}

القرار Decision: {random.choice(['Recommended', 'On Hold', 'Second Interview'])}
المحاور Interviewer: {generate_name('english')[0]}""",
            "format": "interview_notes"
        },
    ]

    doc = random.choice(templates)()
    return {
        "text": doc["text"],
        "classification": "C2",
        "format": doc["format"]
    }


# =============================================================================
# C3 - HIGHLY SENSITIVE (PII, financial data, ID numbers)
# =============================================================================

def generate_c3_document() -> Dict:
    """Generate C3 document - contains National ID, IBAN, passport, or salary"""
    name_full, first, last, email_name = generate_name("mixed")
    national_id = generate_national_id()
    passport = generate_passport()
    iban = generate_iban()
    phone = generate_phone()
    email = f"{email_name}@bankmisr.com"
    salary_egp_amount, salary_egp_str = generate_salary_egp()
    salary_usd_amount, salary_usd_str = generate_salary_usd()
    dept_en = random.choice(DEPARTMENTS_EN)
    dept_ar = DEPARTMENTS_AR[DEPARTMENTS_EN.index(dept_en)]
    position_en = random.choice(POSITIONS_EN)
    date = datetime.now().strftime('%Y-%m-%d')

    templates = [
        # Salary certificate
        lambda: {
            "text": f"""شهادة راتب - Salary Certificate

بيانات الموظف Employee Data:
الاسم Name: {name_full}
الرقم القومي National ID: {national_id}
رقم الحساب IBAN: {iban}
القسم Department: {dept_ar} / {dept_en}

البيانات المالية Financial:
الراتب الأساسي Basic Salary: {salary_egp_str}
البدلات Allowances: {random.randint(1000, 5000):,} EGP
صافي الراتب Net: {salary_egp_amount + random.randint(1000, 5000):,} جنيه

تاريخ الإصدار Issue Date: {date}
صالحة Valid for: 30 days يوم

الغرض Purpose: {random.choice(['فيزا Visa Application', 'قرض Loan', 'إيجار Rental'])}

ختم البنك Bank Seal: __________
التوقيع Signature: __________""",
            "format": "salary_certificate"
        },
        # HR record
        lambda: {
            "text": f"""سجل الموارد البشرية - HR Record

بيانات الموظف Employee Information:
الاسم Name: {name_full}
الرقم القومي National ID: {national_id}
جواز السفر Passport: {passport}
الهاتف Phone: {phone}
البريد Email: {email}

الوظيفة Employment:
المنصب Position: {position_en}
القسم Department: {dept_en}
تاريخ التعيين Hire Date: {(datetime.now() - timedelta(days=random.randint(365, 3650))).strftime('%Y-%m-%d')}

التعويضات Compensation:
الراتب الأساسي Base: {salary_egp_str}
المكافأة السنوية Bonus: {random.randint(10, 25)}%
المزايا Benefits: تأمين طبي، تأمين حياة Medical, Life Insurance

البيانات البنكية Bank:
IBAN: {iban}

جهة اتصال الطوارئ Emergency:
{generate_name('arabic')[0]} - {generate_phone()}""",
            "format": "hr_record"
        },
        # Payroll report
        lambda: {
            "text": f"""تقرير الرواتب - Payroll Report

الفترة Period: {random.choice(['يناير January', 'فبراير February', 'مارس March', 'أبريل April'])} 2025
القسم Department: {dept_en}

سجلات الموظفين Employee Records:

1. {name_full}
   الرقم القومي ID: {national_id}
   الراتب الإجمالي Gross: {salary_usd_str}
   الصافي Net: ${salary_usd_amount - random.randint(500, 2000):,}

2. {generate_name('english')[0]}
   الرقم القومي ID: {generate_national_id()}
   الراتب الإجمالي Gross: ${random.randint(3000, 8000):,}
   الصافي Net: ${random.randint(2500, 7000):,}

3. {generate_name('arabic')[0]}
   الرقم القومي ID: {generate_national_id()}
   الراتب الإجمالي Gross: {random.randint(15000, 50000):,} EGP
   الصافي Net: {random.randint(12000, 45000):,} جنيه

إجمالي الرواتب Total: ${salary_usd_amount + random.randint(5000, 15000):,}

المعتمد Approved: __________
التاريخ Date: {date}""",
            "format": "payroll"
        },
        # Account statement request
        lambda: {
            "text": f"""طلب كشف حساب - Account Statement Request

بيانات العميل Customer:
الاسم Name: {name_full}
الرقم القومي National ID: {national_id}
رقم الحساب IBAN: {iban}
الهاتف Phone: {phone}

تفاصيل الطلب Request:
الفترة Period: آخر 6 أشهر Last 6 months
الغرض Purpose: {random.choice(['طلب فيزا Visa', 'طلب قرض Loan', 'تدقيق Audit', 'سجلات شخصية Personal'])}
طريقة الاستلام Delivery: {random.choice(['استلام من الفرع Branch', 'بريد إلكتروني Email', 'بريد عادي Mail'])}

رصيد الحساب Balance (as of {date}):
الرصيد الحالي Current: {random.randint(10000, 500000):,} EGP

تم التحقق Verified: __________
موظف البنك Officer: {generate_name('english')[0]}""",
            "format": "account_statement"
        },
        # Loan application
        lambda: {
            "text": f"""طلب قرض - Loan Application

بيانات مقدم الطلب Applicant:
الاسم Name: {name_full}
الرقم القومي National ID: {national_id}
جواز السفر Passport: {passport}
الهاتف Phone: {phone}
البريد Email: {email}

بيانات العمل Employment:
جهة العمل Employer: Bank Misr
المنصب Position: {position_en}
الراتب الشهري Monthly Salary: {salary_egp_str}

تفاصيل القرض Loan:
المبلغ Amount: {random.randint(100000, 1000000):,} EGP
الغرض Purpose: {random.choice(['سيارة Car', 'منزل Home', 'شخصي Personal', 'تجاري Business'])}
المدة Term: {random.randint(12, 60)} months شهر

حساب الصرف Disbursement:
IBAN: {iban}

توقيع مقدم الطلب Applicant: __________
التاريخ Date: {date}""",
            "format": "loan_application"
        },
        # Security incident
        lambda: {
            "text": f"""تقرير حادث أمني - Security Incident

معرف الحادث ID: SEC-2025-{random.randint(1000, 9999)}
التاريخ Date: {date}
الخطورة Severity: {random.choice(['حرج Critical', 'عالي High', 'متوسط Medium'])}

بيانات العميل المتأثر Affected Customer:
الاسم Name: {name_full}
الرقم القومي National ID: {national_id}
الحساب IBAN: {iban}
الهاتف Phone: {phone}

وصف الحادث Description:
{random.choice([
    'تم اكتشاف محاولة وصول غير مصرح به على حساب العميل.',
    'تم تحديد معاملة مشبوهة ووضعها قيد المراجعة.',
    'تم التعرف على تعرض محتمل للبيانات.',
    'تم الإبلاغ عن نشاط احتيالي من قبل العميل.'
])}

الإجراء المتخذ Action:
- تجميد الحساب مؤقتاً Account frozen
- تم إخطار العميل Customer notified
- بدء التحقيق Investigation initiated

فريق الأمن Security Team: __________
المتابعة Follow-up: {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}""",
            "format": "security_incident"
        },
        # Executive compensation
        lambda: {
            "text": f"""تقرير تعويضات تنفيذية - Executive Compensation

المدير Executive: {name_full}
المنصب Position: {random.choice(['CEO الرئيس التنفيذي', 'CFO المدير المالي', 'COO مدير العمليات', 'CTO مدير التقنية'])}
الرقم القومي National ID: {national_id}
جواز السفر Passport: {passport}

حزمة التعويضات Compensation:
الراتب الأساسي Base: {salary_usd_str}/month شهرياً
المكافأة السنوية Annual Bonus: ${random.randint(50000, 200000):,}
خيارات الأسهم Stock Options: {random.randint(10000, 50000)} shares سهم
المزايا Benefits: سيارة، سكن، عضوية نادي Car, Housing, Club

البيانات البنكية Bank:
IBAN: {iban}

موافقة مجلس الإدارة Board Approval: __________
التاريخ Date: {date}""",
            "format": "executive_comp"
        },
        # Bank transfer
        lambda: {
            "text": f"""تحويل بنكي - Bank Transfer

المرسل Sender:
الاسم Name: {name_full}
الرقم القومي ID: {national_id}
الحساب From IBAN: {iban}

المستلم Beneficiary:
الاسم Name: {generate_name('english')[0]}
الحساب To IBAN: {generate_iban()}

تفاصيل التحويل Transfer:
المبلغ Amount: {random.randint(5000, 100000):,} EGP
الغرض Purpose: {random.choice(['تحويل عائلي Family', 'دفع فاتورة Bill', 'شراء Purchase', 'إيجار Rent'])}
التاريخ Date: {date}
الرقم المرجعي Ref: TRF-{random.randint(100000, 999999)}

رسوم التحويل Fees: {random.randint(10, 50)} EGP

توقيع العميل Customer: __________
موظف البنك Teller: {generate_name('arabic')[0]}""",
            "format": "bank_transfer"
        },
    ]

    doc = random.choice(templates)()
    return {
        "text": doc["text"],
        "classification": "C3",
        "format": doc["format"]
    }


# =============================================================================
# CHALLENGE DOCUMENTS (edge cases)
# =============================================================================

def generate_challenge_document() -> Dict:
    """Generate edge case documents that test classifier boundaries"""
    challenges = [
        # 13-digit number (NOT a National ID)
        {
            "text": f"""Reference: {random.randint(1000000000000, 9999999999999)}
This is an internal tracking number for order processing.
رقم التتبع الداخلي لمعالجة الطلبات.""",
            "classification": "C1",
            "challenge": "13-digit number (not National ID)"
        },
        # Salary range (public job posting)
        {
            "text": f"""وظيفة شاغرة - Job Opening
Salary range: 15,000-25,000 EGP monthly based on experience
الراتب: 15,000-25,000 جنيه شهرياً حسب الخبرة
Apply: careers@bankmisr.com""",
            "classification": "C0",
            "challenge": "Salary range in public job posting"
        },
        # Redacted/masked data
        {
            "text": f"""Customer Reference:
Name: Ahmed M.
Phone: 010****5678
Account: EG38**********************002
Partial data for reference only - بيانات جزئية للمرجع فقط""",
            "classification": "C1",
            "challenge": "Partially redacted data"
        },
        # Training material about sensitive data
        {
            "text": f"""مواد تدريبية - Training Material
Topic: Handling Customer Data

Examples of data formats (DO NOT COPY):
- National ID: 2YYMMDDGGSSSSSC (14 digits)
- IBAN: EGXXXXXXXXXXXXXXXXXXXXXXXXXXXX

This is educational content for staff training only.
هذا محتوى تعليمي للتدريب فقط.""",
            "classification": "C1",
            "challenge": "Training about sensitive data formats"
        },
        # Non-Egyptian IBAN
        {
            "text": f"""International Transfer:
Beneficiary IBAN: DE89370400440532013000
Amount: 5,000 EUR
Purpose: Vendor payment
تحويل دولي لمورد خارجي""",
            "classification": "C2",
            "challenge": "Non-Egyptian IBAN"
        },
        # Old/archived reference
        {
            "text": f"""Archived Record - سجل مؤرشف
Employee: {generate_name('english')[0]}
Status: File closed 2020
Note: All personal data destroyed per retention policy.
ملاحظة: تم إتلاف جميع البيانات الشخصية وفقاً لسياسة الاحتفاظ.""",
            "classification": "C1",
            "challenge": "Reference to destroyed records"
        },
        # System-generated ID
        {
            "text": f"""System Log:
Transaction ID: 29912011234567890
Timestamp: {datetime.now().isoformat()}
Status: Completed
Note: This is a system-generated ID, not a National ID.
ملاحظة: هذا رقم نظام وليس رقم قومي.""",
            "classification": "C1",
            "challenge": "System ID similar to National ID format"
        },
    ]

    return random.choice(challenges)


# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_diverse_dataset(
    num_documents: int = 100,
    distribution: Dict[str, float] = None
) -> List[Dict]:
    """
    Generate diverse test dataset with specified distribution

    Args:
        num_documents: Total number of documents to generate
        distribution: Dict with C0, C1, C2, C3 percentages (should sum to ~1.0)
    """
    if distribution is None:
        distribution = {"C0": 0.15, "C1": 0.25, "C2": 0.25, "C3": 0.30, "challenge": 0.05}

    documents = []
    generators = {
        "C0": generate_c0_document,
        "C1": generate_c1_document,
        "C2": generate_c2_document,
        "C3": generate_c3_document,
        "challenge": generate_challenge_document,
    }

    for level, percentage in distribution.items():
        count = int(num_documents * percentage)
        for i in range(count):
            doc = generators[level]()
            doc["id"] = f"DOC_{len(documents) + 1:03d}"
            documents.append(doc)

    # Shuffle for randomness
    random.shuffle(documents)

    # Re-assign IDs after shuffle
    for i, doc in enumerate(documents):
        doc["id"] = f"DOC_{i + 1:03d}"

    return documents


def main():
    """Generate and save diverse test dataset"""
    print("=" * 60)
    print("Diverse Test Dataset Generator")
    print("NO CLASSIFICATION KEYWORDS - content-based only")
    print("=" * 60)

    # Generate dataset
    num_docs = 100
    documents = generate_diverse_dataset(num_docs)

    # Count by classification
    counts = {}
    for doc in documents:
        level = doc["classification"]
        counts[level] = counts.get(level, 0) + 1

    print(f"\nGenerated {len(documents)} documents:")
    for level in sorted(counts.keys()):
        print(f"  {level}: {counts[level]} documents ({counts[level]/len(documents)*100:.1f}%)")

    # Save to file
    output_file = "diverse_test_dataset.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {output_file}")

    # Show sample documents
    print("\n" + "=" * 60)
    print("SAMPLE DOCUMENTS (no classification keywords):")
    print("=" * 60)

    for level in ["C0", "C1", "C2", "C3"]:
        sample = next((d for d in documents if d["classification"] == level), None)
        if sample:
            print(f"\n--- {level} Sample ({sample.get('format', 'N/A')}) ---")
            text_preview = sample["text"][:250].replace('\n', ' ')
            print(f"{text_preview}...")


if __name__ == "__main__":
    main()
