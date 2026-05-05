#!/usr/bin/env python3
"""
Flag Manager — Human review / CISO override system.

Flags are stored inline in the document's own JSON file under the 'flag' key.
This keeps all document state in one place without a separate database.

Flow:
  1. Employee calls create_flag() → document gets flag.status = 'PENDING'
  2. CISO calls resolve_flag() with action='MAINTAIN' or 'OVERRIDE'
     - OVERRIDE also updates final_classification in the document
  3. Flag becomes flag.status = 'RESOLVED'
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STORAGE_DIR = os.path.join(_BASE_DIR, 'storage', 'secure_storage')

VALID_CLASSIFICATIONS = {'C0', 'C1', 'C2', 'C3'}
RESOLUTION_ACTIONS = {'MAINTAIN', 'OVERRIDE'}


def _doc_path(doc_id: str, storage_dir: str = None) -> str:
    return os.path.join(storage_dir or _STORAGE_DIR, f"{doc_id}.json")


def _load_doc(doc_id: str, storage_dir: str = None) -> dict:
    path = _doc_path(doc_id, storage_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Document '{doc_id}' not found in storage")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_doc(doc_id: str, data: dict, storage_dir: str = None) -> None:
    path = _doc_path(doc_id, storage_dir)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_flag(
    doc_id: str,
    flagged_by_id: str,
    flagged_by_name: str,
    comment: str,
    suggested_classification: Optional[str] = None,
    storage_dir: str = None,
) -> dict:
    """
    Attach a PENDING flag to a document.
    Raises ValueError if the document already has a pending flag.
    Returns the created flag dict.
    """
    if suggested_classification and suggested_classification not in VALID_CLASSIFICATIONS:
        raise ValueError(f"Invalid suggested_classification: '{suggested_classification}'. "
                         f"Must be one of {sorted(VALID_CLASSIFICATIONS)}")

    data = _load_doc(doc_id, storage_dir)
    existing = data.get('flag')
    if existing and existing.get('status') == 'PENDING':
        raise ValueError("This document already has a pending flag. "
                         "Wait for the CISO to resolve it before flagging again.")

    flag = {
        'flag_id': str(uuid.uuid4()),
        'status': 'PENDING',
        'flagged_by_id': flagged_by_id,
        'flagged_by_name': flagged_by_name,
        'flagged_at': datetime.now(timezone.utc).isoformat(),
        'comment': comment,
        'suggested_classification': suggested_classification,
        # Resolution fields (null until resolved)
        'resolved_by_id': None,
        'resolved_by_name': None,
        'resolved_at': None,
        'resolution_action': None,
        'resolution_comment': None,
        'override_classification': None,
    }
    data['flag'] = flag
    _save_doc(doc_id, data, storage_dir)
    return flag


def resolve_flag(
    doc_id: str,
    resolved_by_id: str,
    resolved_by_name: str,
    action: str,
    comment: str,
    override_classification: Optional[str] = None,
    storage_dir: str = None,
) -> dict:
    """
    Resolve a pending flag.
    action must be 'MAINTAIN' (keep AI classification) or 'OVERRIDE' (change it).
    If OVERRIDE, also updates final_classification and classification in the document.
    Returns the updated flag dict.
    """
    action = action.upper()
    if action not in RESOLUTION_ACTIONS:
        raise ValueError(f"action must be one of {sorted(RESOLUTION_ACTIONS)}")
    if action == 'OVERRIDE':
        if not override_classification or override_classification not in VALID_CLASSIFICATIONS:
            raise ValueError(
                f"OVERRIDE requires a valid override_classification "
                f"({sorted(VALID_CLASSIFICATIONS)})"
            )

    data = _load_doc(doc_id, storage_dir)
    flag = data.get('flag')
    if not flag:
        raise ValueError(f"Document '{doc_id}' has no flag to resolve")
    if flag.get('status') != 'PENDING':
        raise ValueError(f"Flag is already resolved (status: {flag.get('status')})")

    flag['status'] = 'RESOLVED'
    flag['resolved_by_id'] = resolved_by_id
    flag['resolved_by_name'] = resolved_by_name
    flag['resolved_at'] = datetime.now(timezone.utc).isoformat()
    flag['resolution_action'] = action
    flag['resolution_comment'] = comment
    flag['override_classification'] = override_classification if action == 'OVERRIDE' else None

    if action == 'OVERRIDE' and override_classification:
        data['final_classification'] = override_classification
        data['classification'] = override_classification

    data['flag'] = flag
    _save_doc(doc_id, data, storage_dir)
    return flag


def get_flag(doc_id: str, storage_dir: str = None) -> Optional[dict]:
    """Return the flag dict for a document, or None if the document has no flag."""
    try:
        data = _load_doc(doc_id, storage_dir)
        return data.get('flag')
    except FileNotFoundError:
        return None


def ciso_override(
    doc_id: str,
    overridden_by_id: str,
    overridden_by_name: str,
    new_classification: str,
    reasoning: str,
    storage_dir: str = None,
) -> dict:
    """
    CISO directly overrides the classification of any document, with mandatory reasoning.
    The reasoning is stored for future LLM fine-tuning / improvement.
    Returns a summary dict.
    """
    if new_classification not in VALID_CLASSIFICATIONS:
        raise ValueError(
            f"Invalid classification '{new_classification}'. "
            f"Must be one of {sorted(VALID_CLASSIFICATIONS)}"
        )
    if not reasoning or not reasoning.strip():
        raise ValueError("Reasoning is required for a CISO override")

    data = _load_doc(doc_id, storage_dir)
    old_classification = data.get('final_classification') or data.get('classification', '')

    override_record = {
        'overridden_by_id': overridden_by_id,
        'overridden_by_name': overridden_by_name,
        'overridden_at': datetime.now(timezone.utc).isoformat(),
        'old_classification': old_classification,
        'new_classification': new_classification,
        'reasoning': reasoning.strip(),
    }

    # Update classification fields
    data['final_classification'] = new_classification
    data['classification'] = new_classification

    # Append to human_overrides list (preserves full history for LLM training)
    if 'human_overrides' not in data:
        data['human_overrides'] = []
    data['human_overrides'].append(override_record)

    _save_doc(doc_id, data, storage_dir)
    return override_record


def find_doc_by_flag_id(flag_id: str, storage_dir: str = None) -> Optional[str]:
    """
    Scan storage to find the doc_id whose flag matches flag_id.
    Returns doc_id string or None.
    """
    sdir = storage_dir or _STORAGE_DIR
    if not os.path.exists(sdir):
        return None
    for filename in os.listdir(sdir):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(sdir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
        flag = data.get('flag')
        if flag and flag.get('flag_id') == flag_id:
            return data.get('doc_id') or filename[:-5]
    return None


def get_all_flagged(
    status_filter: Optional[str] = None,
    storage_dir: str = None,
) -> List[dict]:
    """
    Scan all documents in storage and return those that have flags.
    Optional status_filter: 'PENDING' or 'RESOLVED'.
    Results are sorted newest-first by flagged_at.
    """
    sdir = storage_dir or _STORAGE_DIR
    results = []

    if not os.path.exists(sdir):
        return results

    for filename in os.listdir(sdir):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(sdir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        flag = data.get('flag')
        if not flag:
            continue
        if status_filter and flag.get('status') != status_filter:
            continue

        results.append({
            'doc_id': data.get('doc_id') or filename[:-5],
            'original_filename': data.get('original_filename'),
            'classification': data.get('final_classification') or data.get('classification'),
            'timestamp': data.get('timestamp'),
            'department': data.get('department'),
            'document_type': data.get('document_type'),
            'flag': flag,
        })

    results.sort(key=lambda x: x['flag'].get('flagged_at', ''), reverse=True)
    return results
