#!/usr/bin/env python3
"""
Calculate Trigger Specificity from Dataset

This script analyzes the training dataset to calculate how uniquely
each trigger identifies a specific classification level.

Method: Based on TF-IDF (Term Frequency - Inverse Document Frequency)
Reference: Salton & Buckley (1988). "Term-weighting approaches in
           automatic text retrieval". Information Processing & Management.

Specificity Formula:
    Specificity(trigger, class) = P(class | trigger)
                                = Count(trigger in class) / Count(trigger total)

A trigger with 95% specificity for C3 means:
    "When this trigger appears, 95% of the time it's a C3 document"
"""

import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple

# Import security rules to get the actual trigger patterns
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security_rules import SecurityRules


def load_dataset(dataset_path: str) -> List[Dict]:
    """Load the training dataset."""
    documents = []

    # Try JSON format
    if dataset_path.endswith('.json'):
        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                documents = data
            elif isinstance(data, dict) and 'documents' in data:
                documents = data['documents']

    # Try JSONL format
    elif dataset_path.endswith('.jsonl'):
        with open(dataset_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    documents.append(json.loads(line))

    return documents


def analyze_trigger_specificity(documents: List[Dict], rules: SecurityRules) -> Dict:
    """
    Analyze how often each trigger appears in each classification level.

    Returns specificity scores based on actual data.
    """
    # Count trigger occurrences per class
    trigger_class_counts = defaultdict(lambda: defaultdict(int))
    trigger_total_counts = defaultdict(int)
    class_counts = defaultdict(int)

    for doc in documents:
        text = doc.get('text', '')
        label = doc.get('label', doc.get('classification', ''))

        if not text or not label:
            continue

        class_counts[label] += 1

        # Check which triggers fire for this document
        text_lower = text.lower()

        # C3 triggers - PII patterns
        if rules._has_national_id(text):
            trigger_class_counts['National ID'][label] += 1
            trigger_total_counts['National ID'] += 1

        if rules._has_passport(text):
            trigger_class_counts['Passport'][label] += 1
            trigger_total_counts['Passport'] += 1

        if rules._has_iban(text):
            trigger_class_counts['IBAN'][label] += 1
            trigger_total_counts['IBAN'] += 1

        if rules._has_credit_card(text):
            trigger_class_counts['Credit Card'][label] += 1
            trigger_total_counts['Credit Card'] += 1

        if rules._has_salary_info(text):
            trigger_class_counts['Salary'][label] += 1
            trigger_total_counts['Salary'] += 1

        if rules._has_account_number(text):
            trigger_class_counts['Account Number'][label] += 1
            trigger_total_counts['Account Number'] += 1

        # C2 triggers - Personal data
        if rules._has_personal_data(text):
            trigger_class_counts['Personal Data'][label] += 1
            trigger_total_counts['Personal Data'] += 1

        # Contract detection
        contract_keywords = ['contract', 'employment agreement', 'عقد عمل', 'عقد توظيف']
        if any(kw in text_lower for kw in contract_keywords):
            trigger_class_counts['Contract'][label] += 1
            trigger_total_counts['Contract'] += 1

        # C1 triggers - Internal
        internal_keywords = rules.internal_keywords if hasattr(rules, 'internal_keywords') else [
            'internal', 'memo', 'meeting', 'staff', 'employees only'
        ]
        if any(kw in text_lower for kw in internal_keywords):
            trigger_class_counts['Internal keywords'][label] += 1
            trigger_total_counts['Internal keywords'] += 1

        # C0 triggers - Public
        public_keywords = rules.public_keywords if hasattr(rules, 'public_keywords') else [
            'public', 'announcement', 'press release', 'customers'
        ]
        if any(kw in text_lower for kw in public_keywords):
            trigger_class_counts['Public keywords'][label] += 1
            trigger_total_counts['Public keywords'] += 1

    # Calculate specificity for each trigger
    # Specificity = P(target_class | trigger) = count(trigger in target_class) / count(trigger total)
    specificity_results = {}

    for trigger, class_counts_for_trigger in trigger_class_counts.items():
        total = trigger_total_counts[trigger]
        if total == 0:
            continue

        # Find the class this trigger most often indicates
        max_class = max(class_counts_for_trigger, key=class_counts_for_trigger.get)
        max_count = class_counts_for_trigger[max_class]

        # Specificity = how often trigger correctly identifies this class
        specificity = max_count / total

        specificity_results[trigger] = {
            'target_class': max_class,
            'specificity': round(specificity, 3),
            'total_occurrences': total,
            'distribution': dict(class_counts_for_trigger),
            'calculation': f"{max_count}/{total} = {specificity:.1%}"
        }

    return {
        'trigger_specificity': specificity_results,
        'class_distribution': dict(class_counts),
        'total_documents': len(documents)
    }


def generate_specificity_code(results: Dict) -> str:
    """Generate Python code for the specificity dictionary."""
    lines = ["# Auto-generated from dataset analysis",
             "# Method: P(class | trigger) from training data",
             "TRIGGER_SPECIFICITY = {"]

    for trigger, data in results['trigger_specificity'].items():
        spec = data['specificity']
        target = data['target_class']
        calc = data['calculation']
        lines.append(f"    '{trigger}': {{'class': '{target}', 'specificity': {spec}}},  # {calc}")

    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 70)
    print("TRIGGER SPECIFICITY ANALYSIS")
    print("Based on: Salton & Buckley (1988) - TF-IDF Term Weighting")
    print("=" * 70)

    # Find dataset
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(base_dir, "data", "diverse_classification_dataset.json"),
        os.path.join(base_dir, "data", "training_data.json"),
        os.path.join(base_dir, "data", "dataset.json"),
    ]

    dataset_path = None
    for path in possible_paths:
        if os.path.exists(path):
            dataset_path = path
            break

    if not dataset_path:
        print("ERROR: No dataset found!")
        print("Looked in:", possible_paths)
        exit(1)

    print(f"\nLoading dataset: {dataset_path}")
    documents = load_dataset(dataset_path)
    print(f"Loaded {len(documents)} documents")

    # Initialize security rules
    rules = SecurityRules()

    # Analyze
    print("\nAnalyzing trigger specificity...")
    results = analyze_trigger_specificity(documents, rules)

    print(f"\nDataset Distribution:")
    for cls, count in sorted(results['class_distribution'].items()):
        pct = count / results['total_documents'] * 100
        print(f"  {cls}: {count} documents ({pct:.1f}%)")

    print(f"\n{'='*70}")
    print("TRIGGER SPECIFICITY RESULTS")
    print("Specificity = P(class | trigger) = 'When trigger fires, probability of this class'")
    print("="*70)

    for trigger, data in sorted(results['trigger_specificity'].items(),
                                 key=lambda x: x[1]['specificity'], reverse=True):
        print(f"\n{trigger}:")
        print(f"  Target Class: {data['target_class']}")
        print(f"  Specificity:  {data['specificity']:.1%} ({data['calculation']})")
        print(f"  Distribution: {data['distribution']}")

    print(f"\n{'='*70}")
    print("GENERATED CODE FOR confidence_scoring.py:")
    print("="*70)
    print(generate_specificity_code(results))
