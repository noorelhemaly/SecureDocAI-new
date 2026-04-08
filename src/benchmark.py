#!/usr/bin/env python3
"""
Blockchain Protection A/B Testing & Performance Benchmark Framework
Measures the runtime overhead, CPU/memory cost, and concurrent-user impact
of adding blockchain document protection to the classification pipeline.
"""
import csv
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

# Graceful psutil import
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Ensure src is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_trail import AuditTrail


# ============================================================================
# Thread-safe wrapper for AuditTrail (needed for concurrent benchmarks)
# ============================================================================

class ThreadSafeAuditWrapper:
    """Wraps AuditTrail with a lock for safe concurrent access."""

    def __init__(self, audit_trail: AuditTrail):
        self._audit = audit_trail
        self._lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self._audit, name)

    def log_event(self, event_type: str, data: Dict):
        with self._lock:
            return self._audit.log_event(event_type, data)

    def _mine_pending_events(self):
        with self._lock:
            return self._audit._mine_pending_events()

    def force_mine_block(self):
        with self._lock:
            return self._audit.force_mine_block()


# ============================================================================
# Resource Monitor — background thread sampling CPU% and memory
# ============================================================================

class ResourceMonitor:
    """Samples CPU and memory usage in a background thread."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.samples_cpu: List[float] = []
        self.samples_mem: List[float] = []

    def start(self):
        if not PSUTIL_AVAILABLE:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> Dict:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

        if not self.samples_cpu:
            return {'cpu_avg': 0, 'cpu_max': 0, 'mem_avg_mb': 0, 'mem_max_mb': 0, 'samples': 0}

        return {
            'cpu_avg': round(sum(self.samples_cpu) / len(self.samples_cpu), 1),
            'cpu_max': round(max(self.samples_cpu), 1),
            'mem_avg_mb': round(sum(self.samples_mem) / len(self.samples_mem), 1),
            'mem_max_mb': round(max(self.samples_mem), 1),
            'samples': len(self.samples_cpu),
        }

    def _sample_loop(self):
        proc = psutil.Process(os.getpid())
        while self._running:
            try:
                self.samples_cpu.append(proc.cpu_percent(interval=None))
                mem_info = proc.memory_info()
                self.samples_mem.append(mem_info.rss / (1024 * 1024))
            except Exception:
                pass
            time.sleep(self.interval)


# ============================================================================
# Helper: classify one document (lightweight — avoids full pipeline overhead)
# ============================================================================

def _classify_single(text: str, pipeline, settings: Dict,
                     enable_protection: bool = False,
                     timing: bool = False) -> Dict:
    """
    Run a single document through the pipeline.
    Returns classification result + optional stage timings.
    """
    doc_id = f"BENCH_{os.urandom(4).hex()}"

    timings = {}
    t0 = time.perf_counter()

    # Call pipeline.process_document with blockchain protection flag
    result = pipeline.process_document(
        doc_id=doc_id,
        text=text,
        confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
        hybrid_mode=settings.get('hybridMode', 'conservative'),
        auto_escalate=settings.get('autoEscalate', True),
        auto_encrypt=settings.get('autoEncryptC2C3', True),
        enable_blockchain_protection=enable_protection,
        timing_mode=timing,
    )

    total_ms = (time.perf_counter() - t0) * 1000

    out = {
        'doc_id': doc_id,
        'classification': result['stages']['classification']['classification'],
        'total_ms': round(total_ms, 2),
    }

    # Extract stage timings if available
    if 'stage_timings' in result:
        out['stage_timings'] = result['stage_timings']

    return out


# ============================================================================
# A/B Test Runner
# ============================================================================

class ABTestRunner:
    """
    Runs the same documents through Mode A (no protection) and Mode B (with
    protection), comparing classifications and timing.
    """

    def __init__(self, pipeline, settings: Dict = None):
        self.pipeline = pipeline
        self.settings = settings or {
            'confidenceThreshold': 85,
            'hybridMode': 'conservative',
            'autoEscalate': True,
            'autoEncryptC2C3': True,
        }

    def run(self, documents: List[Dict], output_dir: str = None) -> Dict:
        """
        Run A/B test on given documents.

        Args:
            documents: List of dicts with 'text' key (and optional 'id')
            output_dir: Directory to write CSV/JSON results

        Returns:
            Summary dict with per-doc comparison and aggregate stats
        """
        if output_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "results", "benchmarks")
        os.makedirs(output_dir, exist_ok=True)

        results = []
        classification_changes = 0

        for i, doc in enumerate(documents):
            text = doc.get('text', '')
            doc_label = doc.get('id', doc.get('doc_id', f'DOC_{i+1:03d}'))
            if not text:
                continue

            # Mode A: without blockchain protection
            res_a = _classify_single(
                text, self.pipeline, self.settings,
                enable_protection=False, timing=True,
            )

            # Mode B: with blockchain protection
            res_b = _classify_single(
                text, self.pipeline, self.settings,
                enable_protection=True, timing=True,
            )

            same_class = res_a['classification'] == res_b['classification']
            if not same_class:
                classification_changes += 1

            row = {
                'doc_id': doc_label,
                'mode_a_classification': res_a['classification'],
                'mode_b_classification': res_b['classification'],
                'same_classification': same_class,
                'mode_a_total_ms': res_a['total_ms'],
                'mode_b_total_ms': res_b['total_ms'],
                'overhead_ms': round(res_b['total_ms'] - res_a['total_ms'], 2),
                'mode_a_timings': res_a.get('stage_timings', {}),
                'mode_b_timings': res_b.get('stage_timings', {}),
            }
            results.append(row)

        # Aggregate
        if results:
            a_times = [r['mode_a_total_ms'] for r in results]
            b_times = [r['mode_b_total_ms'] for r in results]
            avg_a = sum(a_times) / len(a_times)
            avg_b = sum(b_times) / len(b_times)
            overhead_pct = ((avg_b - avg_a) / avg_a * 100) if avg_a > 0 else 0
        else:
            avg_a = avg_b = overhead_pct = 0

        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_documents': len(results),
            'classification_changes': classification_changes,
            'avg_time_without_ms': round(avg_a, 2),
            'avg_time_with_ms': round(avg_b, 2),
            'overhead_pct': round(overhead_pct, 1),
            'results': results,
        }

        # Write CSV
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join(output_dir, f"ab_test_{ts}.csv")
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'doc_id', 'mode', 'classification',
                'classification_ms', 'encryption_ms', 'blockchain_ms', 'total_ms',
            ])
            for r in results:
                for mode_key, mode_label in [('mode_a', 'A'), ('mode_b', 'B')]:
                    timings = r.get(f'{mode_key}_timings', {})
                    writer.writerow([
                        r['doc_id'],
                        mode_label,
                        r[f'{mode_key}_classification'],
                        timings.get('classification_ms', ''),
                        timings.get('encryption_ms', ''),
                        timings.get('blockchain_protection_ms', ''),
                        r[f'{mode_key}_total_ms'],
                    ])

        # Write JSON
        json_path = os.path.join(output_dir, f"ab_test_{ts}.json")
        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)

        summary['csv_path'] = csv_path
        summary['json_path'] = json_path

        return summary


# ============================================================================
# Full Performance Benchmark
# ============================================================================

class PerformanceBenchmark:
    """
    Sequential (N docs) + concurrent (variable user counts) testing.
    Produces JSON report with recommendation.
    """

    def __init__(self, pipeline, settings: Dict = None):
        self.pipeline = pipeline
        self.settings = settings or {
            'confidenceThreshold': 85,
            'hybridMode': 'conservative',
            'autoEscalate': True,
            'autoEncryptC2C3': True,
        }

    def run(self, documents: List[Dict],
            concurrent_levels: List[int] = None,
            output_dir: str = None) -> Dict:
        """
        Run full benchmark suite.

        Args:
            documents: List of dicts with 'text' key
            concurrent_levels: List of concurrent user counts to test (default [5,10,15,20,25])
            output_dir: Directory to write results
        """
        if concurrent_levels is None:
            concurrent_levels = [5, 10, 15, 20, 25]
        if output_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "results", "benchmarks")
        os.makedirs(output_dir, exist_ok=True)

        report = {
            'timestamp': datetime.now().isoformat(),
            'total_documents': len(documents),
            'psutil_available': PSUTIL_AVAILABLE,
        }

        # --- Sequential benchmark ---
        report['sequential'] = {
            'without': self._run_sequential(documents, enable_protection=False),
            'with': self._run_sequential(documents, enable_protection=True),
        }

        seq_without = report['sequential']['without']['avg_ms']
        seq_with = report['sequential']['with']['avg_ms']
        if seq_without > 0:
            report['sequential']['overhead_pct'] = round(
                (seq_with - seq_without) / seq_without * 100, 1
            )
        else:
            report['sequential']['overhead_pct'] = 0

        # --- Concurrent benchmark ---
        report['concurrent'] = {}
        for n_users in concurrent_levels:
            key = f"{n_users}_users"
            report['concurrent'][key] = self._run_concurrent(
                documents, n_users, enable_protection=True
            )

        # --- Recommendation ---
        report['recommendation'] = self._generate_recommendation(report)

        # Write report
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(output_dir, f"benchmark_{ts}.json")
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)

        report['json_path'] = json_path
        return report

    def _run_sequential(self, documents: List[Dict],
                        enable_protection: bool) -> Dict:
        """Run documents sequentially, measuring time and resources."""
        monitor = ResourceMonitor()
        monitor.start()

        times = []
        errors = 0

        for doc in documents:
            text = doc.get('text', '')
            if not text:
                continue
            try:
                res = _classify_single(
                    text, self.pipeline, self.settings,
                    enable_protection=enable_protection, timing=True,
                )
                times.append(res['total_ms'])
            except Exception:
                errors += 1

        resources = monitor.stop()

        if times:
            avg_ms = sum(times) / len(times)
            total_ms = sum(times)
        else:
            avg_ms = total_ms = 0

        return {
            'documents_processed': len(times),
            'errors': errors,
            'total_ms': round(total_ms, 2),
            'avg_ms': round(avg_ms, 2),
            'min_ms': round(min(times), 2) if times else 0,
            'max_ms': round(max(times), 2) if times else 0,
            **resources,
        }

    def _run_concurrent(self, documents: List[Dict], n_users: int,
                        enable_protection: bool) -> Dict:
        """Run documents concurrently with n_users threads."""
        monitor = ResourceMonitor()
        monitor.start()

        times = []
        errors = 0

        # Use thread-safe audit wrapper
        if hasattr(self.pipeline, 'audit') and not isinstance(self.pipeline.audit, ThreadSafeAuditWrapper):
            original_audit = self.pipeline.audit
            self.pipeline.audit = ThreadSafeAuditWrapper(original_audit)
            restore_audit = True
        else:
            restore_audit = False

        def process_one(doc):
            text = doc.get('text', '')
            if not text:
                return None
            return _classify_single(
                text, self.pipeline, self.settings,
                enable_protection=enable_protection, timing=True,
            )

        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=n_users) as executor:
            futures = {executor.submit(process_one, doc): doc for doc in documents}
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        times.append(res['total_ms'])
                except Exception:
                    errors += 1

        wall_time_ms = (time.perf_counter() - start) * 1000
        resources = monitor.stop()

        # Restore original audit
        if restore_audit:
            self.pipeline.audit = original_audit

        if times:
            avg_ms = sum(times) / len(times)
            throughput = len(times) / (wall_time_ms / 1000) if wall_time_ms > 0 else 0
        else:
            avg_ms = throughput = 0

        return {
            'concurrent_users': n_users,
            'documents_processed': len(times),
            'errors': errors,
            'wall_time_ms': round(wall_time_ms, 2),
            'avg_ms_per_doc': round(avg_ms, 2),
            'throughput_docs_per_sec': round(throughput, 2),
            **resources,
        }

    @staticmethod
    def _generate_recommendation(report: Dict) -> Dict:
        """
        Generate recommendation based on benchmark results.

        Thresholds:
        - PROCEED: overhead <30%, concurrent capacity >=20 users, zero classification changes
        - MODIFY: overhead 30-100% or capacity 15-19
        - ABANDON: overhead >100% or capacity <15 or classification changes
        """
        overhead_pct = report['sequential'].get('overhead_pct', 0)

        # Determine max concurrent capacity (highest user count without errors > 10%)
        max_capacity = 0
        for key, data in report.get('concurrent', {}).items():
            n_users = data.get('concurrent_users', 0)
            total = data.get('documents_processed', 0) + data.get('errors', 0)
            error_rate = data.get('errors', 0) / total if total > 0 else 0
            if error_rate <= 0.1:  # <=10% error rate
                max_capacity = max(max_capacity, n_users)

        # Default to highest tested if no errors anywhere
        if max_capacity == 0 and report.get('concurrent'):
            # Check if all levels had zero errors
            all_clean = all(
                d.get('errors', 0) == 0
                for d in report.get('concurrent', {}).values()
            )
            if all_clean:
                max_capacity = max(
                    d.get('concurrent_users', 0)
                    for d in report['concurrent'].values()
                )

        decision = 'PROCEED'
        reasons = []

        if overhead_pct > 100:
            decision = 'ABANDON'
            reasons.append(f'Overhead {overhead_pct:.1f}% exceeds 100% threshold')
        elif overhead_pct > 30:
            decision = 'MODIFY'
            reasons.append(f'Overhead {overhead_pct:.1f}% exceeds 30% threshold (30-100% range)')

        if max_capacity < 15:
            decision = 'ABANDON'
            reasons.append(f'Max concurrent capacity {max_capacity} < 15 users')
        elif max_capacity < 20:
            if decision != 'ABANDON':
                decision = 'MODIFY'
            reasons.append(f'Max concurrent capacity {max_capacity} is below 20 users (15-19 range)')

        if not reasons:
            reasons.append(f'Overhead {overhead_pct:.1f}% within limits, capacity {max_capacity} users OK')

        return {
            'decision': decision,
            'overhead_pct': round(overhead_pct, 1),
            'max_concurrent_capacity': max_capacity,
            'reasons': reasons,
        }


# ============================================================================
# Convenience: load sample documents for benchmarking
# ============================================================================

def load_benchmark_documents(count: int = 50) -> List[Dict]:
    """Load documents from the diverse test dataset for benchmarking."""
    import random
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for filename in ('diverse_test_dataset.json', 'synthetic_training_dataset.json'):
        filepath = os.path.join(base_dir, 'data', filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                all_docs = json.load(f)
            count = min(count, len(all_docs))
            return random.sample(all_docs, count)

    # Fallback: generate minimal test documents
    return [{'text': f'Test document {i} for benchmark', 'id': f'BENCH_{i:03d}'}
            for i in range(count)]
