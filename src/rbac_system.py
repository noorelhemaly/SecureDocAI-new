#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) System
For SecureDoc AI — Three-Department Banking Classification System

Author: Noor Elhemaly (202300013)
Advisor: Dr. Haitham Ghalwash

Departments: Finance, Marketing, HR
Special roles: CISO (All departments, full access)
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


# ============================================================================
# USER CLASS
# ============================================================================

class User:
    """Represents a user in the system"""

    def __init__(self, user_id: str, name: str, access_level: int, role: str,
                 department: str = None, username: str = None, password: str = None):
        self.user_id = user_id
        self.username = username or user_id
        self.password = password or ''
        self.name = name
        self.access_level = access_level  # 1-5
        self.role = role
        self.department = department
        self.created_at = datetime.now()

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'name': self.name,
            'access_level': self.access_level,
            'role': self.role,
            'department': self.department,
            'created_at': self.created_at.isoformat()
        }

    def is_ciso(self) -> bool:
        return self.access_level >= 5 or self.role == 'CISO'

    def is_dpo(self) -> bool:
        """Data Protection Officer — PDPL Art. 4 compliance role."""
        return self.role == 'DPO'

    def has_cross_dept_access(self) -> bool:
        """CISO and DPO both have cross-department access."""
        return self.is_ciso() or self.is_dpo()


# ============================================================================
# FIELD-LEVEL VISIBILITY (level-based, simplified for 3-department model)
# ============================================================================
#
# References:
#   - Egypt PDPL Law No. 151/2020: financial & identity data are sensitive.
#   - CBE Financial Cybersecurity Framework (2020): need-to-know + least privilege.
#   - ISO 27001:2022 Annex A 5.15 and NIST SP 800-53 AC-6.
#
# Rules (within department access already granted):
#   L2  Staff   : name, email, phone visible; salary/national_id/iban/passport REDACTED
#   L3  Analyst : name, email, phone, salary visible; national_id/iban/passport REDACTED
#   L4+ Manager : all fields visible
#   L5  CISO    : all fields visible

def get_field_visibility_by_level(access_level: int, role: str) -> dict:
    """
    Return {field: bool} for every sensitive field based purely on level/role.
    True = user can see the field unredacted.

    Field-level redaction rules per specification:
      L1, L2 : name/email/phone visible; dob/address/salary/national_id/iban/
                account_number/passport/risk_rating/source_of_funds/sanctions REDACTED
      L3      : L2 fields + dob/address/salary visible; national_id/iban/
                account_number/passport/risk_rating/source_of_funds/sanctions REDACTED
      L4+     : all fields visible
      L5/CISO : all fields visible
    """
    _all_visible = {
        'national_id':    True,
        'passport':       True,
        'iban':           True,
        'account_number': True,
        'salary':         True,
        'phone':          True,
        'email':          True,
        'name':           True,
        'date_of_birth':  True,
        'address':        True,
        'risk_rating':    True,
        'source_of_funds': True,
        'sanctions_result': True,
    }

    if access_level >= 4 or role == 'DPO':
        return dict(_all_visible)

    if access_level == 3:
        return {
            'national_id':    False,
            'passport':       False,
            'iban':           False,
            'account_number': False,
            'salary':         True,   # L3 can see salary
            'phone':          True,
            'email':          True,
            'name':           True,
            'date_of_birth':  True,
            'address':        True,
            'risk_rating':    False,
            'source_of_funds': False,
            'sanctions_result': False,
        }

    # L1 and L2
    return {
        'national_id':    False,
        'passport':       False,
        'iban':           False,
        'account_number': False,
        'salary':         False,
        'phone':          True,
        'email':          True,
        'name':           True,
        'date_of_birth':  False,
        'address':        False,
        'risk_rating':    False,
        'source_of_funds': False,
        'sanctions_result': False,
    }


# ============================================================================
# DEPARTMENT-AWARE ACCESS CONTROL
# ============================================================================

def check_document_access(user: 'User', classification: str, doc_department: str, action: str) -> dict:
    """
    Access rules:
      C0: all users, all departments
      C1: all authenticated users (L2+)
      C2: own department + L3+, OR CISO
      C3: own department + L3+ (with heavy redaction at L3), OR CISO

    Only CISO (level >= 5) bypasses the department check.

    Returns {'allowed': bool, 'reason': str}
    """
    if user is None:
        return {'allowed': False, 'reason': 'User not found'}

    lvl = user.access_level
    dept = user.department

    # CISO and DPO have full cross-department access to all classification levels.
    # DPO requires full visibility to verify correct PDPL handling (Art. 4, Law 151/2020).
    if user.is_ciso():
        return {'allowed': True, 'reason': 'CISO has full access'}
    if user.is_dpo():
        return {'allowed': True, 'reason': 'DPO has full cross-department access (PDPL Art. 4)'}

    # L1 viewers only get C0
    if lvl < 2:
        if classification == 'C0':
            return {'allowed': True, 'reason': 'Public document'}
        return {'allowed': False, 'reason': 'Insufficient access level'}

    # C0: all authenticated users
    if classification == 'C0':
        return {'allowed': True, 'reason': 'Public document, all users allowed'}

    # C1: all authenticated users (L2+)
    if classification == 'C1':
        return {'allowed': True, 'reason': 'Internal document, all authenticated users allowed'}

    # C2: own department + L3 only
    if classification == 'C2':
        if lvl < 3:
            return {'allowed': False, 'reason': 'C2 requires minimum Level 3'}
        if dept == doc_department or dept == 'All':
            return {'allowed': True, 'reason': f'Same department ({dept}) with L{lvl} access'}
        return {'allowed': False, 'reason': f'C2 restricted to own department ({doc_department})'}

    # C3: own department + L3 (with heavy redaction) or L4+ full access
    if classification == 'C3':
        if lvl < 3:
            return {'allowed': False, 'reason': 'C3 requires minimum Level 3 within your department'}
        if dept == doc_department or dept == 'All':
            return {'allowed': True, 'reason': f'Same department ({dept}) with L{lvl} access'}
        return {'allowed': False, 'reason': f'C3 restricted to own department ({doc_department})'}

    return {'allowed': False, 'reason': 'Unknown classification'}


def can_download_doc(user: 'User', classification: str, doc_department: str) -> bool:
    """Download follows the same access rules as viewing."""
    return check_document_access(user, classification, doc_department, 'view')['allowed']


# ============================================================================
# LEGACY ACCESS CONTROL MATRIX (kept for backward compatibility)
# ============================================================================

class AccessControlMatrix:
    ACCESS_MATRIX = {
        1: {'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': False, 'download': False, 'print': False},
            'C2': {'view': False, 'download': False, 'print': False},
            'C3': {'view': False, 'download': False, 'print': False}},
        2: {'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': False, 'download': False, 'print': False},
            'C3': {'view': False, 'download': False, 'print': False}},
        3: {'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': True,  'download': False, 'print': False},
            'C3': {'view': False, 'download': False, 'print': False}},
        4: {'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': True,  'download': True,  'print': True},
            'C3': {'view': True,  'download': False, 'print': False}},
        5: {'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': True,  'download': True,  'print': True},
            'C3': {'view': True,  'download': True,  'print': True}},
    }

    @staticmethod
    def can_access(access_level: int, classification: str, action: str):
        if access_level not in AccessControlMatrix.ACCESS_MATRIX:
            return False
        if classification not in AccessControlMatrix.ACCESS_MATRIX[access_level]:
            return False
        return AccessControlMatrix.ACCESS_MATRIX[access_level][classification].get(action, False)


# ============================================================================
# RBAC SYSTEM
# ============================================================================

class RBACSystem:
    """Main RBAC system for users and access control"""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.access_matrix = AccessControlMatrix()

    def add_user(self, user_id: str, name: str, access_level: int, role: str,
                 department: str = None, username: str = None, password: str = None) -> User:
        if access_level < 1 or access_level > 5:
            raise ValueError("Access level must be between 1 and 5")
        user = User(user_id, name, access_level, role, department, username, password)
        self.users[user_id] = user
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Find user by username and verify password. Returns User or None."""
        for user in self.users.values():
            if user.username == username and user.password == password:
                return user
        return None

    def check_access(self, user_id: str, classification: str, action: str,
                     doc_department: str = None) -> Dict:
        """
        Check access using the new department-aware rules when doc_department is provided,
        otherwise fall back to legacy level-only matrix.
        """
        user = self.get_user(user_id)
        if not user:
            return {
                'allowed': False,
                'reason': 'User not found',
                'requires_approval': False,
                'user_level': None,
                'classification': classification,
                'action': action
            }

        if doc_department is not None:
            result = check_document_access(user, classification, doc_department, action)
            # Layered: view allowed → check download separately
            if result['allowed'] and action == 'download':
                if not can_download_doc(user, classification, doc_department):
                    result = {'allowed': False, 'reason': 'Download not permitted for this classification/level'}
            return {
                'allowed': result['allowed'],
                'reason': result['reason'],
                'requires_approval': False,
                'user_level': user.access_level,
                'classification': classification,
                'action': action,
                'user_name': user.name
            }

        # Legacy path (no department info)
        access = self.access_matrix.can_access(user.access_level, classification, action)
        if access:
            return {
                'allowed': True,
                'reason': f'User level {user.access_level} has {action} access to {classification}',
                'requires_approval': False,
                'user_level': user.access_level,
                'classification': classification,
                'action': action,
                'user_name': user.name
            }
        return {
            'allowed': False,
            'reason': f'User level {user.access_level} does not have {action} access to {classification}',
            'requires_approval': False,
            'user_level': user.access_level,
            'classification': classification,
            'action': action,
            'user_name': user.name
        }

    def get_field_visibility(self, user_id: str) -> dict:
        """Return {field: bool} for every sensitive field."""
        user = self.get_user(user_id)
        if not user:
            return {f: False for f in ['national_id', 'passport', 'iban', 'salary', 'phone', 'email']}
        return get_field_visibility_by_level(user.access_level, user.role)

    def can_see_field(self, user_id: str, field_type: str) -> bool:
        return self.get_field_visibility(user_id).get(field_type, False)

    def get_accessible_classifications(self, user_id: str, action: str = 'view') -> List[str]:
        user = self.get_user(user_id)
        if not user:
            return []
        accessible = []
        for cls in ['C0', 'C1', 'C2', 'C3']:
            if self.access_matrix.can_access(user.access_level, cls, action):
                accessible.append(cls)
        return accessible

    def save_users(self, filepath: str):
        users_data = {uid: user.to_dict() for uid, user in self.users.items()}
        with open(filepath, 'w') as f:
            json.dump(users_data, f, indent=2)

    def load_users(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                users_data = json.load(f)
            for uid, data in users_data.items():
                self.users[uid] = User(
                    user_id=data['user_id'],
                    name=data['name'],
                    access_level=data['access_level'],
                    role=data['role'],
                    department=data.get('department'),
                    username=data.get('username', data['user_id']),
                    password=data.get('password', ''),
                )
        except FileNotFoundError:
            pass
