#!/usr/bin/env python3
"""
Blockchain Document Protection System
Independent blockchain for document integrity protection.
Hashes document content + classification metadata and stores in its own chain,
enabling tamper detection via re-hashing and comparison.

Storage files (in storage/audit_logs/):
  protection_chain.json   — the protection blockchain
  protection_pending.json — events waiting to be mined
"""
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from audit_trail import Block


class DocumentProtectionChain:
    """
    Independent blockchain for document integrity protection.
    - protect_document(): hashes content + metadata, stores in own chain
    - verify_document(): re-hashes and compares against stored chain entry
    - Completely separate from the AuditTrail blockchain
    """

    def __init__(self, storage_dir: str = None, difficulty: int = 2,
                 block_size: int = 10):
        if storage_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(base_dir, "storage", "secure_storage")
        self.storage_dir = storage_dir

        # Audit logs directory for chain storage
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.chain_dir = os.path.join(base_dir, "storage", "audit_logs")
        os.makedirs(self.chain_dir, exist_ok=True)

        # Blockchain properties
        self.difficulty = difficulty
        self.block_size = block_size
        self.chain: List[Block] = []
        self.pending_events: List[Dict] = []

        # In-memory index: doc_id -> content_hash
        self._protection_index: Dict[str, str] = {}
        # In-memory index: doc_id -> classification (for encrypted-doc tamper check)
        self._classification_index: Dict[str, str] = {}

        # Load existing chain and pending events
        self._load_chain()
        self._load_pending_events()

        # Create genesis block if chain is empty
        if not self.chain:
            self._create_genesis_block()

        # Rebuild index from chain
        self._rebuild_index()

    # ------------------------------------------------------------------
    # Chain persistence
    # ------------------------------------------------------------------

    def _create_genesis_block(self):
        """Create the first block in the protection chain."""
        genesis = Block(
            index=0,
            events=[{
                'event_type': 'GENESIS',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'message': 'SecureDoc AI Document Protection Chain Initialized',
                    'version': '1.0',
                    'algorithm': 'SHA-256 with Proof-of-Work',
                }
            }],
            previous_hash="0" * 64,
            difficulty=self.difficulty,
        )
        self.chain.append(genesis)
        self._save_chain()

    def _load_chain(self):
        """Load protection blockchain from storage."""
        chain_file = os.path.join(self.chain_dir, "protection_chain.json")
        if os.path.exists(chain_file):
            try:
                with open(chain_file, 'r') as f:
                    chain_data = json.load(f)
                    if chain_data:
                        self.chain = []
                        for block_data in chain_data:
                            block = Block(
                                index=block_data['index'],
                                events=block_data['events'],
                                previous_hash=block_data['previous_hash'],
                                difficulty=block_data.get('difficulty', self.difficulty),
                                timestamp=block_data['timestamp'],
                            )
                            block.hash = block_data['hash']
                            block.nonce = block_data['nonce']
                            block.merkle_root = block_data['merkle_root']
                            self.chain.append(block)
            except Exception as e:
                print(f"Warning: Could not load protection chain: {e}")

    def _save_chain(self):
        """Save entire protection blockchain to file."""
        chain_file = os.path.join(self.chain_dir, "protection_chain.json")
        chain_data = [b.to_dict() for b in self.chain]
        with open(chain_file, 'w') as f:
            json.dump(chain_data, f, indent=2)

    def _load_pending_events(self):
        """Load pending protection events from storage."""
        pending_file = os.path.join(self.chain_dir, "protection_pending.json")
        if os.path.exists(pending_file):
            try:
                with open(pending_file, 'r') as f:
                    self.pending_events = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load protection pending events: {e}")
                self.pending_events = []

    def _save_pending_events(self):
        """Save pending protection events to disk."""
        pending_file = os.path.join(self.chain_dir, "protection_pending.json")
        with open(pending_file, 'w') as f:
            json.dump(self.pending_events, f, indent=2)

    def _mine_pending(self):
        """Mine pending events into a new block."""
        if not self.pending_events:
            return None

        previous_block = self.chain[-1] if self.chain else None
        previous_hash = previous_block.hash if previous_block else "0" * 64

        new_block = Block(
            index=len(self.chain),
            events=self.pending_events.copy(),
            previous_hash=previous_hash,
            difficulty=self.difficulty,
        )

        self.chain.append(new_block)
        self.pending_events = []
        self._save_chain()
        self._save_pending_events()

        return new_block

    def force_mine_block(self) -> Optional[Block]:
        """Force mine pending events into a new block."""
        if self.pending_events:
            return self._mine_pending()
        return None

    # ------------------------------------------------------------------
    # Chain verification & status
    # ------------------------------------------------------------------

    def verify_chain(self) -> Dict:
        """Verify the protection blockchain integrity."""
        result = {
            'valid': True,
            'blocks_verified': 0,
            'invalid_blocks': [],
            'errors': [],
        }

        for i, block in enumerate(self.chain):
            previous_hash = self.chain[i - 1].hash if i > 0 else "0" * 64
            verification = block.verify(previous_hash)

            if not all(verification.values()):
                result['valid'] = False
                result['invalid_blocks'].append(i)
                for check, passed in verification.items():
                    if not passed:
                        result['errors'].append(f"Block {i}: {check} failed")
            else:
                result['blocks_verified'] += 1

        return result

    def get_chain_status(self) -> Dict:
        """Get current protection chain status for API consumption."""
        verification = self.verify_chain()
        return {
            'chain_length': len(self.chain),
            'total_events': sum(len(b.events) for b in self.chain),
            'pending_events': len(self.pending_events),
            'difficulty': self.difficulty,
            'last_block_hash': self.chain[-1].hash if self.chain else None,
            'last_block_time': self.chain[-1].timestamp if self.chain else None,
            'chain_valid': verification['valid'],
            'algorithm': 'SHA-256 + Proof-of-Work',
            'consensus': 'Proof-of-Work (PoW)',
        }

    # ------------------------------------------------------------------
    # Protection index
    # ------------------------------------------------------------------

    def _rebuild_index(self):
        """Scan own chain for DOCUMENT_PROTECTED events to rebuild index."""
        all_events = [e for block in self.chain for e in block.events] + self.pending_events
        for event in all_events:
            if event.get('event_type') == 'DOCUMENT_PROTECTED':
                data = event.get('data', {})
                doc_id = data.get('document_id')
                content_hash = data.get('content_hash')
                classification = data.get('classification')
                if doc_id:
                    if content_hash:
                        self._protection_index[doc_id] = content_hash
                    if classification:
                        self._classification_index[doc_id] = classification

    # ------------------------------------------------------------------
    # Document hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_document(content: str, classification: str, doc_id: str,
                      metadata: Dict = None) -> str:
        """
        Create SHA-256 hash of document content + classification metadata.
        Deterministic: same inputs always produce same hash.
        """
        hash_input = {
            'doc_id': doc_id,
            'content': content,
            'classification': classification,
        }
        if metadata:
            for key in ('classification_method', 'triggers', 'confidence'):
                if key in metadata:
                    hash_input[key] = metadata[key]

        hash_string = json.dumps(hash_input, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()

    # ------------------------------------------------------------------
    # Protect & Verify
    # ------------------------------------------------------------------

    def protect_document(self, doc_id: str, content: str, classification: str,
                         metadata: Dict = None, user_id: str = None) -> Dict:
        """
        Protect a document by hashing its content and logging to the
        protection chain.
        """
        start = time.perf_counter()

        content_hash = self.hash_document(content, classification, doc_id, metadata)

        # Store in index
        self._protection_index[doc_id] = content_hash

        # Log to own chain
        event_data = {
            'document_id': doc_id,
            'content_hash': content_hash,
            'classification': classification,
            'hash_algorithm': 'SHA-256',
            'protected_at': datetime.now().isoformat(),
        }
        if user_id:
            event_data['user_id'] = user_id

        self._log_event('DOCUMENT_PROTECTED', event_data)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            'doc_id': doc_id,
            'content_hash': content_hash,
            'classification': classification,
            'protected': True,
            'elapsed_ms': round(elapsed_ms, 2),
        }

    def verify_document(self, doc_id: str, content: str = None,
                        classification: str = None,
                        metadata: Dict = None) -> Dict:
        """
        Verify document integrity by re-hashing and comparing against
        the protection chain.
        """
        start = time.perf_counter()

        # Get stored hash from index or scan chain
        stored_hash = self._protection_index.get(doc_id)
        if not stored_hash:
            self._rebuild_index()
            stored_hash = self._protection_index.get(doc_id)

        if not stored_hash:
            return {
                'doc_id': doc_id,
                'verified': False,
                'error': 'Document not found in protection chain',
                'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
            }

        # If content not provided, read from storage
        doc_data = None
        if content is None or classification is None or metadata is None:
            doc_data = self._load_stored_document(doc_id)
            if not doc_data and (content is None or classification is None):
                return {
                    'doc_id': doc_id,
                    'verified': False,
                    'error': 'Stored document file not found',
                    'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
                }
            if content is None:
                content = doc_data.get('original_text') or ''
                if not content and doc_data.get('encrypted_data'):
                    # Document is encrypted — original text is not stored in plain form.
                    # Use the ciphertext as the hashable content (consistent with protect_document).
                    enc_data = doc_data.get('encrypted_data', {})
                    ciphertext = enc_data.get('ciphertext', '')
                    if ciphertext:
                        content = ciphertext
                    else:
                        # No ciphertext available; fall back to classification-only check
                        stored_classification = self._classification_index.get(doc_id)
                        if stored_classification is None:
                            self._rebuild_index()
                            stored_classification = self._classification_index.get(doc_id)
                        current_classification = doc_data.get('classification', '')
                        elapsed_ms = (time.perf_counter() - start) * 1000
                        if stored_classification is None:
                            return {
                                'doc_id': doc_id,
                                'verified': None,
                                'encrypted': True,
                                'note': 'Document is encrypted; no verifiable content found.',
                                'stored_hash': stored_hash,
                                'elapsed_ms': round(elapsed_ms, 2),
                            }
                        classification_ok = (current_classification == stored_classification)
                        result = {
                            'doc_id': doc_id,
                            'verified': classification_ok,
                            'encrypted': True,
                            'current_classification': current_classification,
                            'stored_classification': stored_classification,
                            'match': classification_ok,
                            'stored_hash': stored_hash,
                            'elapsed_ms': round(elapsed_ms, 2),
                        }
                        if not classification_ok:
                            result['warning'] = (
                                f'TAMPERING DETECTED: Classification changed from '
                                f'"{stored_classification}" to "{current_classification}" '
                                f'since document was protected.'
                            )
                        self._log_event('DOCUMENT_VERIFIED', {
                            'document_id': doc_id,
                            'verified': classification_ok,
                            'encrypted': True,
                        })
                        return result
            if classification is None:
                classification = doc_data.get('classification', '')
            if metadata is None and doc_data:
                stored_meta = doc_data.get('metadata', {})
                metadata = {
                    'classification_method': stored_meta.get('classification_method'),
                    'triggers': stored_meta.get('triggers'),
                    'confidence': stored_meta.get('confidence'),
                }

        # Recompute hash
        current_hash = self.hash_document(content, classification, doc_id, metadata)

        verified = current_hash == stored_hash
        elapsed_ms = (time.perf_counter() - start) * 1000

        result = {
            'doc_id': doc_id,
            'verified': verified,
            'current_hash': current_hash,
            'stored_hash': stored_hash,
            'match': verified,
            'elapsed_ms': round(elapsed_ms, 2),
        }

        # Log verification event to own chain
        self._log_event('DOCUMENT_VERIFIED', {
            'document_id': doc_id,
            'verified': verified,
            'current_hash': current_hash,
            'stored_hash': stored_hash,
        })

        if not verified:
            result['warning'] = 'TAMPERING DETECTED: Document content has been modified since protection'

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, data: Dict):
        """Add an event to the protection chain's pending events."""
        event = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'data': data,
        }
        self.pending_events.append(event)
        self._save_pending_events()

        # Mine new block if enough events accumulated
        if len(self.pending_events) >= self.block_size:
            self._mine_pending()

    def _load_stored_document(self, doc_id: str) -> Optional[Dict]:
        """Load a document from secure storage."""
        filepath = os.path.join(self.storage_dir, f"{doc_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def protect_document_from_file(self, doc_id: str, user_id: str = None) -> Dict:
        """
        Protect an existing stored document by reading it from storage.
        For encrypted documents, hashes the ciphertext (consistent with the pipeline).
        For plain documents, hashes the original_text.
        """
        doc_data = self._load_stored_document(doc_id)
        if not doc_data:
            return {'protected': False, 'error': f'Document {doc_id} not found in storage'}

        # Determine content to hash
        enc_data = doc_data.get('encrypted_data', {})
        ciphertext = enc_data.get('ciphertext', '') if enc_data else ''
        original_text = doc_data.get('original_text') or ''

        if ciphertext:
            content = ciphertext
        elif original_text:
            content = original_text
        else:
            return {'protected': False, 'error': f'Document {doc_id} has no hashable content'}

        classification = doc_data.get('final_classification') or doc_data.get('classification', '')
        stored_meta = doc_data.get('metadata', {})
        metadata = {
            'classification_method': stored_meta.get('classification_method'),
            'triggers': stored_meta.get('triggers'),
            'confidence': stored_meta.get('confidence'),
        }

        return self.protect_document(
            doc_id=doc_id,
            content=content,
            classification=classification,
            metadata=metadata,
            user_id=user_id,
        )

    def protect_all_from_storage(self, user_id: str = None) -> Dict:
        """
        Retroactively protect all documents found in storage that are not yet indexed.
        Returns counts of protected, skipped (already protected), and failed documents.
        """
        results = {'protected': [], 'skipped': [], 'failed': []}

        if not os.path.exists(self.storage_dir):
            return results

        for filename in os.listdir(self.storage_dir):
            if not filename.endswith('.json'):
                continue
            doc_id = filename[:-5]  # strip .json
            if doc_id in self._protection_index:
                results['skipped'].append(doc_id)
                continue
            try:
                result = self.protect_document_from_file(doc_id, user_id=user_id)
                if result.get('protected'):
                    results['protected'].append(doc_id)
                else:
                    results['failed'].append({'doc_id': doc_id, 'reason': result.get('error')})
            except Exception as e:
                results['failed'].append({'doc_id': doc_id, 'reason': str(e)})

        # Mine all pending events into the chain
        if results['protected']:
            self._mine_pending()

        return results

    def get_protection_status(self) -> Dict:
        """Get summary of all protected documents."""
        return {
            'total_protected': len(self._protection_index),
            'protected_documents': list(self._protection_index.keys()),
        }
