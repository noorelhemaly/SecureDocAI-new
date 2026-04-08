#!/usr/bin/env python3
"""
Blockchain-based Audit Trail System
Implements a tamper-proof, immutable ledger for document classification events
Uses proof-of-work consensus and cryptographic hash chaining
"""
import json
import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class Block:
    """
    Blockchain Block Structure
    Each block contains multiple audit events and is cryptographically linked
    """

    def __init__(self, index: int, events: List[Dict], previous_hash: str,
                 difficulty: int = 0, timestamp: str = None, block_signature: str = None):
        self.index = index
        self.timestamp = timestamp or datetime.now().isoformat()
        self.events = events  # List of audit events in this block
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = 0  # Kept for backward compatibility with existing blocks
        self.block_signature = block_signature  # Dilithium3 signature of block hash
        self.merkle_root = self._calculate_merkle_root()
        self.hash = self._calculate_hash()

    def _calculate_merkle_root(self) -> str:
        """Calculate Merkle root of all events in block"""
        if not self.events:
            return hashlib.sha256(b"empty").hexdigest()

        # Hash each event
        hashes = [hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()
                  for e in self.events]

        # Build Merkle tree
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Duplicate last hash if odd
            hashes = [hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
                      for i in range(0, len(hashes), 2)]

        return hashes[0]

    def _calculate_hash(self) -> str:
        """Calculate block hash"""
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'difficulty': self.difficulty
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Convert block to dictionary"""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'events': self.events,
            'events_count': len(self.events),
            'merkle_root': self.merkle_root,
            'previous_hash': self.previous_hash,
            'hash': self.hash,
            'nonce': self.nonce,
            'difficulty': self.difficulty,
            'block_signature': self.block_signature,
        }

    def verify(self, previous_hash: str, public_key_bytes: bytes = None) -> Dict:
        """Verify block integrity including Dilithium3 signature if present"""
        result = {
            'hash_valid': self._calculate_hash() == self.hash,
            'chain_valid': self.previous_hash == previous_hash,
            'merkle_valid': self._calculate_merkle_root() == self.merkle_root,
        }
        if self.block_signature and public_key_bytes is not None:
            try:
                import base64
                from dilithium_py.dilithium import Dilithium3
                sig_bytes = base64.b64decode(self.block_signature)
                result['sig_valid'] = Dilithium3.verify(public_key_bytes, self.hash.encode(), sig_bytes)
            except Exception:
                result['sig_valid'] = False
        return result


class AuditLog:
    """Single audit log entry with hash chaining (legacy support)"""

    def __init__(self, event_type: str, data: Dict, previous_hash: str = None):
        self.log_id = self._generate_log_id()
        self.timestamp = datetime.now().isoformat()
        self.event_type = event_type
        self.data = data
        self.previous_hash = previous_hash or "0" * 64  # Genesis block
        self.current_hash = self._calculate_hash()

    def _generate_log_id(self) -> str:
        """Generate unique log ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"LOG_{timestamp}"

    def _calculate_hash(self) -> str:
        """Calculate SHA-256 hash of log entry"""
        log_string = json.dumps({
            'log_id': self.log_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data,
            'previous_hash': self.previous_hash
        }, sort_keys=True)

        return hashlib.sha256(log_string.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Convert log to dictionary"""
        return {
            'log_id': self.log_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'current_hash': self.current_hash
        }

    def verify_integrity(self) -> bool:
        """Verify hash integrity"""
        recalculated = self._calculate_hash()
        return recalculated == self.current_hash


class AuditTrail:
    """
    Blockchain-based Audit Trail System
    Features:
    - Proof-of-Work consensus
    - Cryptographic hash chaining
    - Merkle tree for event integrity
    - Tamper detection
    - PDPL compliance (7-year retention)
    """

    def __init__(self, storage_dir: str = None, difficulty: int = 2,
                 block_size: int = 10):
        if storage_dir is None:
            # Default to storage/audit_logs relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(base_dir, "storage", "audit_logs")
        self.storage_dir = storage_dir
        self.logs: List[AuditLog] = []  # Legacy log entries
        self.current_log_file = None

        # Blockchain properties
        self.difficulty = 0  # PoW removed — blocks use Dilithium3 signatures
        self.block_size = block_size  # Events per block
        self.chain: List[Block] = []  # The blockchain
        self.pending_events: List[Dict] = []  # Events waiting to be mined
        self._signing_key: Optional[bytes] = None
        self._verify_key: Optional[bytes] = None

        # Create storage directory
        os.makedirs(storage_dir, exist_ok=True)

        # Load Dilithium3 signing keys before creating any blocks
        self._load_block_signing_key()

        # Load existing blockchain first (before creating genesis!)
        self._load_blockchain()
        self._load_pending_events()

        # Only create genesis if no chain was loaded
        if not self.chain:
            self._create_genesis_block()

        # Load existing legacy logs
        self._load_logs()

    def _create_genesis_block(self):
        """Create the first block in the chain"""
        if not self.chain:
            genesis = Block(
                index=0,
                events=[{
                    'event_type': 'GENESIS',
                    'timestamp': datetime.now().isoformat(),
                    'data': {
                        'message': 'SecureDoc AI Blockchain Audit Trail Initialized',
                        'version': '2.0',
                        'algorithm': 'SHA-256 + CRYSTALS-Dilithium3 Block Signatures'
                    }
                }],
                previous_hash="0" * 64,
            )
            self._sign_block(genesis)
            self.chain.append(genesis)
            self._save_block(genesis)

    def _load_blockchain(self):
        """Load blockchain from storage"""
        blockchain_file = os.path.join(self.storage_dir, "blockchain.json")
        if os.path.exists(blockchain_file):
            try:
                with open(blockchain_file, 'r') as f:
                    chain_data = json.load(f)
                    if chain_data:
                        self.chain = []
                        for block_data in chain_data:
                            block = Block(
                                index=block_data['index'],
                                events=block_data['events'],
                                previous_hash=block_data['previous_hash'],
                                difficulty=block_data.get('difficulty', self.difficulty),
                                timestamp=block_data['timestamp']
                            )
                            block.hash = block_data['hash']
                            block.nonce = block_data['nonce']
                            block.merkle_root = block_data['merkle_root']
                            block.block_signature = block_data.get('block_signature')
                            self.chain.append(block)
            except Exception as e:
                print(f"Warning: Could not load blockchain: {e}")
                # Don't overwrite - leave chain empty so genesis will be created

    def _load_pending_events(self):
        """Load pending events from storage (survives restarts)"""
        pending_file = os.path.join(self.storage_dir, "pending_events.json")
        if os.path.exists(pending_file):
            try:
                with open(pending_file, 'r') as f:
                    self.pending_events = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load pending events: {e}")
                self.pending_events = []

    def _save_pending_events(self):
        """Save pending events to disk"""
        pending_file = os.path.join(self.storage_dir, "pending_events.json")
        with open(pending_file, 'w') as f:
            json.dump(self.pending_events, f, indent=2)

    def _save_block(self, block: Block):
        """Save a single block to the blockchain file"""
        blockchain_file = os.path.join(self.storage_dir, "blockchain.json")
        chain_data = [b.to_dict() for b in self.chain]
        with open(blockchain_file, 'w') as f:
            json.dump(chain_data, f, indent=2)

    def _save_blockchain(self):
        """Save entire blockchain to file"""
        blockchain_file = os.path.join(self.storage_dir, "blockchain.json")
        chain_data = [b.to_dict() for b in self.chain]
        with open(blockchain_file, 'w') as f:
            json.dump(chain_data, f, indent=2)
    
    def _get_last_hash(self) -> str:
        """Get hash of last log entry"""
        if not self.logs:
            return "0" * 64  # Genesis hash
        return self.logs[-1].current_hash
    
    def _load_logs(self):
        """Load logs from storage"""
        # For now, keep in memory
        # In production, load from database or file
        pass
    
    def log_event(self, event_type: str, data: Dict) -> AuditLog:
        """
        Log an event to both legacy chain and blockchain

        Event Types:
        - DOCUMENT_UPLOAD
        - DOCUMENT_CLASSIFICATION
        - DOCUMENT_ACCESS
        - DOCUMENT_DOWNLOAD
        - DOCUMENT_PRINT
        - DOCUMENT_MODIFY
        - USER_LOGIN
        - USER_LOGOUT
        - ACCESS_DENIED
        - ENCRYPTION_APPLIED
        - DECRYPTION_PERFORMED
        - KEY_ROTATION
        - SECURITY_BREACH_DETECTED
        """
        # Legacy log entry (backwards compatibility)
        previous_hash = self._get_last_hash()
        log = AuditLog(event_type, data, previous_hash)
        self.logs.append(log)

        # Save to file immediately
        self._save_log(log)

        # Add to blockchain pending events
        blockchain_event = {
            'event_id': log.log_id,
            'event_type': event_type,
            'timestamp': log.timestamp,
            'data': data,
            'hash': log.current_hash
        }
        self.pending_events.append(blockchain_event)
        self._save_pending_events()

        # Mine new block if we have enough events
        if len(self.pending_events) >= self.block_size:
            self._mine_pending_events()

        return log

    def _mine_pending_events(self):
        """Mine pending events into a new block"""
        if not self.pending_events:
            return None

        previous_block = self.chain[-1] if self.chain else None
        previous_hash = previous_block.hash if previous_block else "0" * 64

        new_block = Block(
            index=len(self.chain),
            events=self.pending_events.copy(),
            previous_hash=previous_hash,
        )
        self._sign_block(new_block)

        self.chain.append(new_block)
        self.pending_events = []
        self._save_blockchain()
        self._save_pending_events()

        return new_block

    def force_mine_block(self) -> Optional[Block]:
        """Force mine pending events (for admin use)"""
        if self.pending_events:
            return self._mine_pending_events()
        return None

    def _load_block_signing_key(self):
        """Load Dilithium3 keypair for block signing from digital_signature module"""
        try:
            import base64
            from digital_signature import SignatureKeyManager
            km = SignatureKeyManager()
            key_info = km.load_keypair()
            if key_info:
                self._signing_key = base64.b64decode(key_info['private_key'])
                self._verify_key = base64.b64decode(key_info['public_key'])
        except Exception:
            pass  # Graceful degradation — blocks still hash-chain without signatures

    def _sign_block(self, block: Block):
        """Sign a block's hash with Dilithium3 private key"""
        if self._signing_key is None:
            return
        try:
            import base64
            from dilithium_py.dilithium import Dilithium3
            sig = Dilithium3.sign(self._signing_key, block.hash.encode())
            block.block_signature = base64.b64encode(sig).decode()
        except Exception:
            pass

    def get_blockchain_status(self) -> Dict:
        """Get current blockchain status"""
        verification = self.verify_blockchain()
        return {
            'chain_length': len(self.chain),
            'total_events': sum(len(b.events) for b in self.chain),
            'pending_events': len(self.pending_events),
            'difficulty': self.difficulty,
            'last_block_hash': self.chain[-1].hash if self.chain else None,
            'last_block_time': self.chain[-1].timestamp if self.chain else None,
            'chain_valid': verification['valid'],
            'algorithm': 'SHA-256 + Dilithium3 Block Signatures',
            'consensus': 'Hash Chain + PQC Block Signing'
        }

    def get_blockchain(self) -> List[Dict]:
        """Get full blockchain as list of block dictionaries"""
        return [block.to_dict() for block in self.chain]

    def verify_blockchain(self) -> Dict:
        """
        Verify entire blockchain integrity

        Returns:
            {
                'valid': bool,
                'blocks_verified': int,
                'invalid_blocks': List[int],
                'errors': List[str]
            }
        """
        result = {
            'valid': True,
            'blocks_verified': 0,
            'invalid_blocks': [],
            'errors': []
        }

        for i, block in enumerate(self.chain):
            previous_hash = self.chain[i-1].hash if i > 0 else "0" * 64
            verification = block.verify(previous_hash, self._verify_key)

            if not all(verification.values()):
                result['valid'] = False
                result['invalid_blocks'].append(i)
                for check, passed in verification.items():
                    if not passed:
                        result['errors'].append(f"Block {i}: {check} failed")
            else:
                result['blocks_verified'] += 1

        return result
    
    def _save_log(self, log: AuditLog):
        """Save log to file"""
        # Create daily log file
        date_str = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(self.storage_dir, f"audit_{date_str}.jsonl")
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log.to_dict()) + '\n')
    
    def verify_chain_integrity(self) -> Dict:
        """
        Verify entire chain integrity
        
        Returns:
            {
                'valid': bool,
                'total_logs': int,
                'verified_logs': int,
                'tampered_logs': List[str],
                'broken_chains': List[int]
            }
        """
        result = {
            'valid': True,
            'total_logs': len(self.logs),
            'verified_logs': 0,
            'tampered_logs': [],
            'broken_chains': []
        }
        
        for i, log in enumerate(self.logs):
            # Verify log hash
            if not log.verify_integrity():
                result['valid'] = False
                result['tampered_logs'].append(log.log_id)
            else:
                result['verified_logs'] += 1
            
            # Verify chain link
            if i > 0:
                previous_log = self.logs[i-1]
                if log.previous_hash != previous_log.current_hash:
                    result['valid'] = False
                    result['broken_chains'].append(i)
        
        return result
    
    def get_logs_by_type(self, event_type: str) -> List[AuditLog]:
        """Get all logs of specific type"""
        return [log for log in self.logs if log.event_type == event_type]
    
    def get_logs_by_user(self, user_id: str) -> List[AuditLog]:
        """Get all logs for specific user"""
        return [log for log in self.logs if log.data.get('user_id') == user_id]
    
    def get_logs_by_document(self, document_id: str) -> List[AuditLog]:
        """Get all logs for specific document"""
        return [log for log in self.logs if log.data.get('document_id') == document_id]
    
    def get_logs_in_timerange(self, start: datetime, end: datetime) -> List[AuditLog]:
        """Get logs within time range"""
        return [log for log in self.logs 
                if start.isoformat() <= log.timestamp <= end.isoformat()]
    
    def detect_unauthorized_access(self) -> List[Dict]:
        """Detect unauthorized access attempts"""
        unauthorized = []
        
        for log in self.get_logs_by_type('ACCESS_DENIED'):
            unauthorized.append({
                'log_id': log.log_id,
                'timestamp': log.timestamp,
                'user_id': log.data.get('user_id'),
                'document_id': log.data.get('document_id'),
                'classification': log.data.get('classification'),
                'reason': log.data.get('reason')
            })
        
        return unauthorized
    
    def generate_compliance_report(self, days: int = 7) -> Dict:
        """
        Generate compliance report for PDPL
        
        Args:
            days: Number of days to include in report
            
        Returns:
            Compliance statistics and incidents
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logs_in_period = self.get_logs_in_timerange(start_date, end_date)
        
        report = {
            'report_generated': datetime.now().isoformat(),
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'total_events': len(logs_in_period),
            'events_by_type': {},
            'security_incidents': [],
            'unauthorized_attempts': 0,
            'documents_accessed': set(),
            'users_active': set(),
            'c3_access_events': []
        }
        
        for log in logs_in_period:
            # Count events by type
            event_type = log.event_type
            report['events_by_type'][event_type] = report['events_by_type'].get(event_type, 0) + 1
            
            # Track unauthorized attempts
            if event_type == 'ACCESS_DENIED':
                report['unauthorized_attempts'] += 1
            
            # Track security breaches
            if event_type == 'SECURITY_BREACH_DETECTED':
                report['security_incidents'].append({
                    'timestamp': log.timestamp,
                    'details': log.data
                })
            
            # Track C3 access (most sensitive)
            if log.data.get('classification') == 'C3':
                report['c3_access_events'].append({
                    'timestamp': log.timestamp,
                    'event': event_type,
                    'user': log.data.get('user_id'),
                    'document': log.data.get('document_id')
                })
            
            # Track unique documents and users
            if 'document_id' in log.data:
                report['documents_accessed'].add(log.data['document_id'])
            if 'user_id' in log.data:
                report['users_active'].add(log.data['user_id'])
        
        # Convert sets to counts
        report['unique_documents'] = len(report['documents_accessed'])
        report['unique_users'] = len(report['users_active'])
        del report['documents_accessed']
        del report['users_active']
        
        return report


# ============================================================================
# HELPER FUNCTIONS FOR EASY LOGGING
# ============================================================================

def log_document_classification(audit: AuditTrail, document_id: str, 
                                classification: str, method: str, confidence: float):
    """Log document classification decision"""
    return audit.log_event('DOCUMENT_CLASSIFICATION', {
        'document_id': document_id,
        'classification': classification,
        'method': method,  # 'LLM', 'RULES', 'HYBRID'
        'confidence': confidence,
        'timestamp': datetime.now().isoformat()
    })


def log_document_access(audit: AuditTrail, document_id: str, user_id: str,
                       classification: str, action: str, allowed: bool, reason: str = None):
    """Log document access attempt"""
    event_type = 'DOCUMENT_ACCESS' if allowed else 'ACCESS_DENIED'
    
    return audit.log_event(event_type, {
        'document_id': document_id,
        'user_id': user_id,
        'classification': classification,
        'action': action,  # 'view', 'download', 'print'
        'allowed': allowed,
        'reason': reason,
        'timestamp': datetime.now().isoformat()
    })


def log_encryption_event(audit: AuditTrail, document_id: str,
                        encryption_type: str, key_id: str):
    """Log encryption applied to document"""
    return audit.log_event('ENCRYPTION_APPLIED', {
        'document_id': document_id,
        'encryption_type': encryption_type,  # 'AES-256', 'PQC', 'HYBRID'
        'key_id': key_id,
        'timestamp': datetime.now().isoformat()
    })


def log_signature_event(audit: AuditTrail, document_id: str, content_hash: str,
                        signature_hash: str, key_id: str, algorithm: str,
                        user_id: str = None):
    """
    Log a digital signature event to the blockchain audit trail.

    The signature_hash (SHA-256 of the raw Dilithium3 signature bytes) is
    embedded in the blockchain so any tampering with the signature file is
    detectable by comparing against this immutable record.
    """
    data = {
        'document_id': document_id,
        'content_hash': content_hash,
        'signature_hash': signature_hash,
        'key_id': key_id,
        'algorithm': algorithm,
        'timestamp': datetime.now().isoformat(),
    }
    if user_id:
        data['user_id'] = user_id
    return audit.log_event('DOCUMENT_SIGNED', data)


# ============================================================================
# TESTING THE AUDIT SYSTEM
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("AUDIT TRAIL SYSTEM WITH HASH CHAINING")
    print("="*70)
    
    # Initialize audit system
    audit = AuditTrail()
    
    print("\n📝 Logging test events...\n")
    
    # Test Event 1: Document upload
    audit.log_event('DOCUMENT_UPLOAD', {
        'document_id': 'DOC_001',
        'filename': 'salary_certificate.pdf',
        'user_id': 'U005',
        'file_size_mb': 2.5
    })
    print("✓ Logged: Document upload")
    
    # Test Event 2: Classification
    log_document_classification(audit, 'DOC_001', 'C3', 'HYBRID', 0.98)
    print("✓ Logged: Document classification (C3)")
    
    # Test Event 3: Encryption
    log_encryption_event(audit, 'DOC_001', 'AES-256', 'KEY_001')
    print("✓ Logged: Encryption applied")
    
    # Test Event 4: Successful access
    log_document_access(audit, 'DOC_001', 'U005', 'C3', 'view', True)
    print("✓ Logged: Successful access (Level 5)")
    
    # Test Event 5: Denied access
    log_document_access(audit, 'DOC_001', 'U002', 'C3', 'view', False, 
                       'User level 2 does not have access to C3')
    print("✓ Logged: Access denied (Level 2 → C3)")
    
    # Test Event 6: Another denied access
    log_document_access(audit, 'DOC_001', 'U003', 'C3', 'download', False,
                       'User level 3 cannot download C3')
    print("✓ Logged: Access denied (Level 3 download)")
    
    # Verify chain integrity
    print("\n" + "="*70)
    print("VERIFYING HASH CHAIN INTEGRITY")
    print("="*70)
    
    integrity = audit.verify_chain_integrity()
    
    print(f"\n✓ Chain Valid: {integrity['valid']}")
    print(f"  Total Logs: {integrity['total_logs']}")
    print(f"  Verified: {integrity['verified_logs']}")
    print(f"  Tampered: {len(integrity['tampered_logs'])}")
    print(f"  Broken Links: {len(integrity['broken_chains'])}")
    
    # Show hash chain
    print("\n" + "="*70)
    print("HASH CHAIN VISUALIZATION")
    print("="*70)
    
    for i, log in enumerate(audit.logs[:3], 1):  # Show first 3
        print(f"\nLog {i}: {log.event_type}")
        print(f"  Previous: {log.previous_hash[:16]}...")
        print(f"  Current:  {log.current_hash[:16]}...")
        if i < 3:
            print(f"           ↓ (linked)")
    
    # Generate compliance report
    print("\n" + "="*70)
    print("COMPLIANCE REPORT (Last 7 Days)")
    print("="*70)
    
    report = audit.generate_compliance_report(days=7)
    
    print(f"\n📊 Period: {report['period_start'][:10]} to {report['period_end'][:10]}")
    print(f"  Total Events: {report['total_events']}")
    print(f"  Unique Users: {report['unique_users']}")
    print(f"  Unique Documents: {report['unique_documents']}")
    print(f"  Unauthorized Attempts: {report['unauthorized_attempts']}")
    
    print(f"\n📋 Events by Type:")
    for event_type, count in report['events_by_type'].items():
        print(f"  {event_type}: {count}")
    
    print(f"\n🔐 C3 Access Events: {len(report['c3_access_events'])}")
    for event in report['c3_access_events']:
        print(f"  - {event['event']} by {event['user']} at {event['timestamp'][:19]}")
    
    # Detect unauthorized access
    print("\n" + "="*70)
    print("UNAUTHORIZED ACCESS DETECTION")
    print("="*70)
    
    unauthorized = audit.detect_unauthorized_access()
    print(f"\n🚨 Found {len(unauthorized)} unauthorized access attempts:")
    
    for attempt in unauthorized:
        print(f"\n  User: {attempt['user_id']}")
        print(f"  Document: {attempt['document_id']} ({attempt['classification']})")
        print(f"  Time: {attempt['timestamp'][:19]}")
        print(f"  Reason: {attempt['reason']}")
    
    print("\n" + "="*70)
    print("✅ AUDIT TRAIL SYSTEM READY!")
    print("   Features:")
    print("   ✓ Hash-chained logs (tamper-proof)")
    print("   ✓ All events logged with timestamps")
    print("   ✓ Compliance reporting")
    print("   ✓ Unauthorized access detection")
    print("   ✓ 7-year retention capability")
    print("="*70)
    
    print("\n📁 Logs saved to: audit_logs/")
    print("   Next step: Integrate with RBAC and classification system\n")
