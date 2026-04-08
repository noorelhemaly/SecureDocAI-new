#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) System
For Egyptian Banking Document Classification

Author: Noor Elhemaly (202300013)
Advisor: Dr. Haitham Ghalwash
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


# ============================================================================
# USER CLASS
# ============================================================================

class User:
    """Represents a user in the system"""
    
    def __init__(self, user_id: str, name: str, access_level: int, role: str, department: str = None):
        self.user_id = user_id
        self.name = name
        self.access_level = access_level  # 1-5
        self.role = role
        self.department = department
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'name': self.name,
            'access_level': self.access_level,
            'role': self.role,
            'department': self.department,
            'created_at': self.created_at.isoformat()
        }


# ============================================================================
# FIELD-LEVEL VISIBILITY (for redaction)
# ============================================================================
#
# References:
#   - Egypt Labor Law No. 14/2025 (replaced 12/2003): HR must hold National ID,
#     Passport, and payroll/salary records for all employees.
#   - Egypt PDPL Law No. 151/2020: financial & identity data are sensitive;
#     processing requires a lawful, role-based purpose.
#   - CBE Financial Cybersecurity Framework (2020): need-to-know + least privilege
#     per ISO 27001:2022 Annex A 5.15 and NIST SP 800-53 AC-6.
#
# Rule: a user may see a field if ANY of these is true:
#   (a) user.access_level >= min_level_override  (CISO / unconditional level gate)
#   (b) user.department in authorized_departments
#   (c) user.role      in authorized_roles

FIELD_VISIBILITY = {
    'national_id': {
        # Required by HR under Labor Law 14/2025; Compliance/Legal for CBE KYC/AML.
        'min_level_override': 5,
        'authorized_departments': ['Human Resources', 'Compliance', 'Legal', 'KYC'],
        'authorized_roles': [
            'HR Officer', 'HR Manager', 'Senior HR Manager',
            'Compliance Officer', 'Legal Officer', 'KYC Officer',
        ],
    },
    'passport': {
        # Required by HR under Labor Law 14/2025 (non-Egyptian employees);
        # Compliance/Legal for identity verification.
        'min_level_override': 5,
        'authorized_departments': ['Human Resources', 'Compliance', 'Legal'],
        'authorized_roles': [
            'HR Officer', 'HR Manager', 'Senior HR Manager',
            'Compliance Officer', 'Legal Officer',
        ],
    },
    'iban': {
        # HR needs IBAN for payroll transfers; Finance for payment processing;
        # Compliance for AML transaction monitoring (CBE framework).
        'min_level_override': 5,
        'authorized_departments': ['Human Resources', 'Finance', 'Accounting', 'Treasury', 'Compliance'],
        'authorized_roles': [
            'HR Officer', 'HR Manager', 'Senior HR Manager',
            'Finance Analyst', 'Finance Manager', 'Head of Finance',
            'Accountant', 'Treasury Officer', 'Compliance Officer',
        ],
    },
    'salary': {
        # HR is the primary data owner; Finance for payroll processing.
        # Compliance / Operations do NOT need individual salary figures.
        'min_level_override': 5,
        'authorized_departments': ['Human Resources', 'Finance', 'Accounting'],
        'authorized_roles': [
            'HR Officer', 'HR Manager', 'Senior HR Manager',
            'Finance Analyst', 'Finance Manager', 'Head of Finance', 'Accountant',
        ],
    },
    'phone': {
        # HR (employment records), Branch / Operations (operational coordination),
        # Customer Service, Compliance/Legal (case investigations).
        # Level 4+ also granted unconditionally.
        'min_level_override': 4,
        'authorized_departments': [
            'Human Resources', 'Operations', 'Customer Service', 'Compliance', 'Legal',
        ],
        'authorized_roles': [
            'HR Officer', 'HR Manager', 'Senior HR Manager',
            'Branch Manager', 'Customer Service Officer',
            'Compliance Officer', 'Legal Officer',
        ],
    },
    'email': {
        # All employees have a legitimate need for email addresses (ISO 27001 A 5.15).
        'min_level_override': 2,
        'authorized_departments': [],   # All departments — level gate is enough
        'authorized_roles': [],
    },
}


# ============================================================================
# ACCESS CONTROL MATRIX
# ============================================================================

class AccessControlMatrix:
    """
    Defines what each access_level can do for each document classification.

    Levels:
      1 – Public Users
      2 – Employees
      3 – Supervisors / Branch Managers
      4 – Senior Managers / Officers
      5 – CISO / Administrators
    """

    ACCESS_MATRIX = {
        1: {  # Public Users — C0 only
            'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': False, 'download': False, 'print': False},
            'C2': {'view': False, 'download': False, 'print': False},
            'C3': {'view': False, 'download': False, 'print': False},
        },
        2: {  # Employees — C0–C1
            'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': False, 'download': False, 'print': False},
            'C3': {'view': False, 'download': False, 'print': False},
        },
        3: {  # Supervisors / Branch Managers — C0–C2 view, no C2 download
            'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': True,  'download': False, 'print': False},
            'C3': {'view': False, 'download': False, 'print': False},
        },
        4: {  # Senior Managers / Officers — C0–C2 full, C3 view-only
            'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': True,  'download': True,  'print': True},
            'C3': {'view': True,  'download': False, 'print': False},
        },
        5: {  # CISO / Administrators — full access
            'C0': {'view': True,  'download': True,  'print': True},
            'C1': {'view': True,  'download': True,  'print': True},
            'C2': {'view': True,  'download': True,  'print': True},
            'C3': {'view': True,  'download': True,  'print': True},
        },
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
    
    def add_user(self, user_id: str, name: str, access_level: int, role: str, department: str = None) -> User:
        """Add a new user"""
        if access_level < 1 or access_level > 5:
            raise ValueError("Access level must be between 1 and 5")
        user = User(user_id, name, access_level, role, department)
        self.users[user_id] = user
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)
    
    def check_access(self, user_id: str, classification: str, action: str) -> Dict:
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
        
        access = self.access_matrix.can_access(user.access_level, classification, action)
        
        if access == 'APPROVAL_REQUIRED':
            return {
                'allowed': False,
                'reason': 'Requires approval from CISO',
                'requires_approval': True,
                'user_level': user.access_level,
                'classification': classification,
                'action': action,
                'user_name': user.name
            }
        elif access:
            return {
                'allowed': True,
                'reason': f'User level {user.access_level} has {action} access to {classification}',
                'requires_approval': False,
                'user_level': user.access_level,
                'classification': classification,
                'action': action,
                'user_name': user.name
            }
        else:
            return {
                'allowed': False,
                'reason': f'User level {user.access_level} does not have {action} access to {classification}',
                'requires_approval': False,
                'user_level': user.access_level,
                'classification': classification,
                'action': action,
                'user_name': user.name
            }
    
    def can_see_field(self, user_id: str, field_type: str) -> bool:
        """
        Return True if this user is allowed to see a sensitive field unredacted.

        field_type is one of: 'national_id', 'passport', 'iban', 'salary', 'phone', 'email'

        Logic (any one condition is sufficient):
          (a) user.access_level >= rule['min_level_override']
          (b) user.department  in rule['authorized_departments']
          (c) user.role        in rule['authorized_roles']
        """
        user = self.get_user(user_id)
        if not user:
            return False

        rule = FIELD_VISIBILITY.get(field_type)
        if rule is None:
            return False  # Unknown field → deny by default

        if user.access_level >= rule['min_level_override']:
            return True
        if user.department and user.department in rule['authorized_departments']:
            return True
        if user.role and user.role in rule['authorized_roles']:
            return True
        return False

    def get_field_visibility(self, user_id: str) -> dict:
        """Return a dict of {field: bool} for every sensitive field."""
        return {field: self.can_see_field(user_id, field) for field in FIELD_VISIBILITY}

    def get_accessible_classifications(self, user_id: str, action: str = 'view') -> List[str]:
        user = self.get_user(user_id)
        if not user:
            return []
        
        accessible = []
        for classification in ['C0', 'C1', 'C2', 'C3']:
            access = self.access_matrix.can_access(user.access_level, classification, action)
            if access == True:
                accessible.append(classification)
            elif access == 'APPROVAL_REQUIRED':
                accessible.append(f"{classification} (approval required)")
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
                    department=data.get('department')
                )
        except FileNotFoundError:
            pass


# ============================================================================
# TESTING RBAC SYSTEM
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("✅ RBAC SYSTEM READY")
    print("="*70)
    
    rbac = RBACSystem()
    
    # Example users
    users = [
        ('U001', 'Public User', 1, 'General Public'),
        ('U002', 'Sara Mohamed', 2, 'Employee'),
        ('U003', 'Ahmed Hassan', 3, 'Manager'),
        ('U004', 'Fatma Ali', 4, 'Senior Manager'),
        ('U005', 'Noor Elhemaly', 5, 'CISO Admin')
    ]
    
    for uid, name, level, role in users:
        rbac.add_user(uid, name, level, role)
    
    # Save to JSON
    rbac.save_users('rbac_users.json')
    print("✓ Users saved to rbac_users.json")
