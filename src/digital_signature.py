#!/usr/bin/env python3
"""
Digital Signature Module for Document Integrity Protection
CRYSTALS-Dilithium3 (ML-DSA-65) post-quantum digital signatures.
Provides non-repudiation (PDPL Article 21), quantum-resistant security,
and follows NIST FIPS 204 (ML-DSA standard).

Storage:
  storage/keys/signature_keys/SIG_DILITHIUM3_DEFAULT.json  — Dilithium3 keypair
  storage/signatures/{doc_id}.json                         — Per-document signatures
"""
import base64
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional

from dilithium_py.dilithium import Dilithium3


# ============================================================================
# Key Management
# ============================================================================

class SignatureKeyManager:
    """Manage CRYSTALS-Dilithium3 keypairs for digital signatures."""

    def __init__(self, key_storage_dir: str = None):
        if key_storage_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            key_storage_dir = os.path.join(base_dir, "storage", "keys", "signature_keys")
        self.key_storage_dir = key_storage_dir
        os.makedirs(self.key_storage_dir, exist_ok=True)

    def generate_keypair(self, key_id: str = None) -> Dict:
        """
        Generate a CRYSTALS-Dilithium3 keypair and store as JSON.

        Args:
            key_id: Identifier for the key (auto-generated if None)

        Returns:
            Key metadata dict with base64-encoded keys
        """
        if key_id is None:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            key_id = f"SIG_DILITHIUM3_{timestamp}"

        pk, sk = Dilithium3.keygen()

        key_metadata = {
            'key_id': key_id,
            'algorithm': 'CRYSTALS-Dilithium3',
            'standard': 'NIST FIPS 204 (ML-DSA-65)',
            'security_level': 'NIST Level 3 (128-bit quantum security)',
            'created_at': datetime.now().isoformat(),
            'public_key': base64.b64encode(pk).decode(),
            'private_key': base64.b64encode(sk).decode(),
            'public_key_bytes': len(pk),
            'private_key_bytes': len(sk),
            'signature_bytes': 3293,
        }

        key_file = os.path.join(self.key_storage_dir, f"{key_id}.json")
        with open(key_file, 'w') as f:
            json.dump(key_metadata, f, indent=2)
        os.chmod(key_file, 0o600)

        return key_metadata

    def get_keypair(self, key_id: str) -> Optional[Dict]:
        """Load a keypair by ID."""
        key_file = os.path.join(self.key_storage_dir, f"{key_id}.json")
        if not os.path.exists(key_file):
            return None
        with open(key_file, 'r') as f:
            return json.load(f)

    def get_or_create_default(self) -> Dict:
        """
        Get the default Dilithium3 keypair, creating it if it doesn't exist.
        Single keypair reused for all documents.
        """
        default_id = "SIG_DILITHIUM3_DEFAULT"
        existing = self.get_keypair(default_id)
        if existing:
            return existing
        return self.generate_keypair(key_id=default_id)

    def _load_private_key(self, key_data: Dict) -> bytes:
        """Deserialize private key bytes from stored base64."""
        return base64.b64decode(key_data['private_key'])

    def _load_public_key(self, key_data: Dict) -> bytes:
        """Deserialize public key bytes from stored base64."""
        return base64.b64decode(key_data['public_key'])


# ============================================================================
# Document Signature Manager
# ============================================================================

class DocumentSignatureManager:
    """
    CRYSTALS-Dilithium3 (ML-DSA-65) digital signatures for document integrity protection.
    Signs document content + classification metadata, stores per-document
    signature files in storage/signatures/.
    """

    def __init__(self, signature_storage_dir: str = None,
                 key_storage_dir: str = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if signature_storage_dir is None:
            signature_storage_dir = os.path.join(base_dir, "storage", "signatures")
        if key_storage_dir is None:
            key_storage_dir = os.path.join(base_dir, "storage", "keys", "signature_keys")

        self.signature_storage_dir = signature_storage_dir
        os.makedirs(self.signature_storage_dir, exist_ok=True)

        self.key_manager = SignatureKeyManager(key_storage_dir)

    # ------------------------------------------------------------------
    # Document hashing (identical to DocumentProtectionChain.hash_document)
    # ------------------------------------------------------------------

    @staticmethod
    def hash_document(content: str, classification: str, doc_id: str,
                      metadata: Dict = None) -> str:
        """
        Create SHA-256 hash of document content + classification metadata.
        Deterministic: same inputs always produce same hash.
        Identical to DocumentProtectionChain.hash_document() for consistency.
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
    # Sign & Verify
    # ------------------------------------------------------------------

    def sign_document(self, doc_id: str, content: str, classification: str,
                      metadata: Dict = None, user_id: str = None) -> Dict:
        """
        Sign a document using CRYSTALS-Dilithium3.

        1. Hash the document (SHA-256, same as blockchain)
        2. Sign the hash with Dilithium3
        3. Save signature to storage/signatures/{doc_id}.json

        Returns:
            Dict with doc_id, content_hash, signature, key_id, algorithm, elapsed_ms
        """
        start = time.perf_counter()

        # Get or create default keypair
        key_data = self.key_manager.get_or_create_default()
        sk = self.key_manager._load_private_key(key_data)

        # Hash document content (identical to blockchain approach)
        content_hash = self.hash_document(content, classification, doc_id, metadata)

        # Dilithium3 signature over the content hash bytes
        hash_bytes = content_hash.encode('utf-8')
        signature = Dilithium3.sign(sk, hash_bytes)
        signature_b64 = base64.b64encode(signature).decode()

        # Hash of the signature itself — stored in the audit trail for tamper detection
        signature_hash = hashlib.sha256(signature).hexdigest()

        # Store signature file
        sig_data = {
            'doc_id': doc_id,
            'content_hash': content_hash,
            'classification': classification,
            'signature': signature_b64,
            'signature_hash': signature_hash,
            'key_id': key_data['key_id'],
            'algorithm': 'CRYSTALS-Dilithium3',
            'standard': 'NIST FIPS 204 (ML-DSA-65)',
            'hash_algorithm': 'SHA-256',
            'signature_bytes': len(signature),
            'signed_at': datetime.now().isoformat(),
        }
        if user_id:
            sig_data['user_id'] = user_id

        sig_file = os.path.join(self.signature_storage_dir, f"{doc_id}.json")
        with open(sig_file, 'w') as f:
            json.dump(sig_data, f, indent=2)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            'doc_id': doc_id,
            'content_hash': content_hash,
            'classification': classification,
            'protected': True,
            'signature': signature_b64,
            'signature_hash': signature_hash,
            'key_id': key_data['key_id'],
            'algorithm': 'CRYSTALS-Dilithium3',
            'standard': 'NIST FIPS 204 (ML-DSA-65)',
            'elapsed_ms': round(elapsed_ms, 2),
        }

    def verify_signature(self, doc_id: str, content: str = None,
                         classification: str = None,
                         metadata: Dict = None) -> Dict:
        """
        Verify a document's RSA-PSS signature.

        1. Load stored signature from storage/signatures/{doc_id}.json
        2. Re-hash the document
        3. Verify RSA-PSS signature using public key

        Returns:
            Dict with doc_id, verified, current_hash, stored_hash, signature_valid, elapsed_ms
        """
        start = time.perf_counter()

        # Load stored signature
        sig_file = os.path.join(self.signature_storage_dir, f"{doc_id}.json")
        if not os.path.exists(sig_file):
            return {
                'doc_id': doc_id,
                'verified': False,
                'error': 'Signature not found for document',
                'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
            }

        with open(sig_file, 'r') as f:
            sig_data = json.load(f)

        stored_hash = sig_data['content_hash']
        signature_b64 = sig_data['signature']
        key_id = sig_data['key_id']

        # If content not provided, try to load from secure storage
        if content is None or classification is None:
            doc_data = self._load_stored_document(doc_id)
            if not doc_data and (content is None or classification is None):
                return {
                    'doc_id': doc_id,
                    'verified': False,
                    'error': 'Stored document file not found; provide content for verification',
                    'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
                }
            if content is None:
                content = doc_data.get('original_text') or ''
                if not content and doc_data.get('encrypted_data'):
                    return {
                        'doc_id': doc_id,
                        'verified': False,
                        'error': 'Document is encrypted; provide decrypted content for verification',
                        'stored_hash': stored_hash,
                        'elapsed_ms': round((time.perf_counter() - start) * 1000, 2),
                    }
            if classification is None:
                classification = doc_data.get('classification', '')
            if metadata is None and doc_data:
                stored_meta = doc_data.get('metadata', {})
                metadata = {
                    'classification_method': stored_meta.get('classification_method'),
                    'triggers': stored_meta.get('triggers'),
                    'confidence': stored_meta.get('confidence'),
                }

        # Re-hash document
        current_hash = self.hash_document(content, classification, doc_id, metadata)
        hash_match = current_hash == stored_hash

        # Verify Dilithium3 signature
        signature_valid = False
        try:
            key_data = self.key_manager.get_keypair(key_id)
            if key_data:
                pk = self.key_manager._load_public_key(key_data)
                signature_bytes = base64.b64decode(signature_b64)
                signature_valid = Dilithium3.verify(pk, stored_hash.encode('utf-8'), signature_bytes)
        except Exception:
            signature_valid = False

        verified = hash_match and signature_valid
        elapsed_ms = (time.perf_counter() - start) * 1000

        result = {
            'doc_id': doc_id,
            'verified': verified,
            'current_hash': current_hash,
            'stored_hash': stored_hash,
            'match': hash_match,
            'signature_valid': signature_valid,
            'algorithm': sig_data.get('algorithm', 'CRYSTALS-Dilithium3'),
            'standard': sig_data.get('standard', 'NIST FIPS 204 (ML-DSA-65)'),
            'elapsed_ms': round(elapsed_ms, 2),
        }

        if not verified:
            if not hash_match:
                result['warning'] = 'TAMPERING DETECTED: Document content has been modified since signing'
            elif not signature_valid:
                result['warning'] = 'SIGNATURE INVALID: Signature verification failed'

        return result

    # ------------------------------------------------------------------
    # Status & helpers
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Get digital signature system status."""
        key_data = self.key_manager.get_or_create_default()

        # Count signed documents
        signed_docs = []
        if os.path.exists(self.signature_storage_dir):
            signed_docs = [f[:-5] for f in os.listdir(self.signature_storage_dir)
                           if f.endswith('.json')]

        return {
            'key_id': key_data['key_id'],
            'algorithm': 'CRYSTALS-Dilithium3',
            'standard': 'NIST FIPS 204 (ML-DSA-65)',
            'security_level': 'NIST Level 3 (128-bit quantum security)',
            'hash_algorithm': 'SHA-256',
            'public_key_bytes': key_data.get('public_key_bytes', 1952),
            'signature_bytes': key_data.get('signature_bytes', 3293),
            'key_created_at': key_data.get('created_at'),
            'total_signed': len(signed_docs),
            'signed_documents': signed_docs,
        }

    def _load_stored_document(self, doc_id: str) -> Optional[Dict]:
        """Load a document from secure storage."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        storage_dir = os.path.join(base_dir, "storage", "secure_storage")
        filepath = os.path.join(storage_dir, f"{doc_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
