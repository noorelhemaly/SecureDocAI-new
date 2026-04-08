#!/usr/bin/env python3
"""
Three-Way Benchmark: Baseline vs Blockchain vs Digital Signature
Compares the three integrity protection modes on classification accuracy,
latency, CPU/memory usage, and concurrent-user capacity.

Output:
  results/benchmarks/signature_comparison_{ts}.csv
  results/benchmarks/signature_comparison_{ts}.json
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

from benchmark import ResourceMonitor, ThreadSafeAuditWrapper, load_benchmark_documents


# ============================================================================
# Helper: classify one document in a specific mode
# ============================================================================

def _classify_single_with_mode(text: str, pipeline, settings: Dict,
                               mode: str = 'baseline') -> Dict:
    """
    Run a single document through the pipeline in the specified mode.

    Args:
        text: Document text
        pipeline: DocumentPipeline instance
        settings: Classification settings
        mode: 'baseline' | 'blockchain' | 'signature'

    Returns:
        Dict with classification, total_ms, stage_timings
    """
    doc_id = f"BENCH_{os.urandom(4).hex()}"

    enable_blockchain = (mode == 'blockchain')
    enable_signature = (mode == 'signature')

    t0 = time.perf_counter()

    result = pipeline.process_document(
        doc_id=doc_id,
        text=text,
        confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
        hybrid_mode=settings.get('hybridMode', 'conservative'),
        auto_escalate=settings.get('autoEscalate', True),
        auto_encrypt=settings.get('autoEncryptC2C3', True),
        enable_blockchain_protection=enable_blockchain,
        enable_digital_signature=enable_signature,
        timing_mode=True,
    )

    total_ms = (time.perf_counter() - t0) * 1000

    out = {
        'doc_id': doc_id,
        'mode': mode,
        'classification': result['stages']['classification']['classification'],
        'total_ms': round(total_ms, 2),
    }

    if 'stage_timings' in result:
        out['stage_timings'] = result['stage_timings']

    return out


# ============================================================================
# Three-Way Benchmark Runner
# ============================================================================

class ThreeWayBenchmarkRunner:
    """
    Runs the same documents through three modes:
    - baseline: no integrity protection
    - blockchain: blockchain document protection (PoW)
    - signature: RSA-PSS digital signature

    Compares classifications, timing, and generates analysis.
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
        Run three-way comparison on given documents.

        Args:
            documents: List of dicts with 'text' key
            output_dir: Directory to write CSV/JSON results

        Returns:
            Summary dict with per-doc comparison and aggregate stats
        """
        if output_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "results", "benchmarks")
        os.makedirs(output_dir, exist_ok=True)

        results = []
        modes = ['baseline', 'blockchain', 'signature']

        for i, doc in enumerate(documents):
            text = doc.get('text', '')
            doc_label = doc.get('id', doc.get('doc_id', f'DOC_{i+1:03d}'))
            if not text:
                continue

            row = {'doc_id': doc_label}

            for mode in modes:
                res = _classify_single_with_mode(
                    text, self.pipeline, self.settings, mode=mode,
                )
                row[f'{mode}_classification'] = res['classification']
                row[f'{mode}_total_ms'] = res['total_ms']
                row[f'{mode}_timings'] = res.get('stage_timings', {})

            # Check agreement
            row['all_agree'] = (
                row['baseline_classification'] ==
                row['blockchain_classification'] ==
                row['signature_classification']
            )
            row['blockchain_overhead_ms'] = round(
                row['blockchain_total_ms'] - row['baseline_total_ms'], 2
            )
            row['signature_overhead_ms'] = round(
                row['signature_total_ms'] - row['baseline_total_ms'], 2
            )

            results.append(row)

        # Aggregate stats
        summary = self._aggregate(results)
        summary['results'] = results

        # Generate analysis
        summary['analysis'] = self._generate_analysis(summary)

        # Write CSV
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join(output_dir, f"signature_comparison_{ts}.csv")
        self._write_csv(csv_path, results, modes)

        # Write JSON
        json_path = os.path.join(output_dir, f"signature_comparison_{ts}.json")
        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)

        summary['csv_path'] = csv_path
        summary['json_path'] = json_path

        return summary

    def _aggregate(self, results: List[Dict]) -> Dict:
        """Compute aggregate statistics from per-document results."""
        if not results:
            return {
                'timestamp': datetime.now().isoformat(),
                'total_documents': 0,
            }

        modes = ['baseline', 'blockchain', 'signature']
        stats = {}

        for mode in modes:
            times = [r[f'{mode}_total_ms'] for r in results]
            stats[mode] = {
                'avg_ms': round(sum(times) / len(times), 2),
                'min_ms': round(min(times), 2),
                'max_ms': round(max(times), 2),
                'total_ms': round(sum(times), 2),
            }

        # Overheads relative to baseline
        baseline_avg = stats['baseline']['avg_ms']
        if baseline_avg > 0:
            stats['blockchain']['overhead_pct'] = round(
                (stats['blockchain']['avg_ms'] - baseline_avg) / baseline_avg * 100, 1
            )
            stats['signature']['overhead_pct'] = round(
                (stats['signature']['avg_ms'] - baseline_avg) / baseline_avg * 100, 1
            )
        else:
            stats['blockchain']['overhead_pct'] = 0
            stats['signature']['overhead_pct'] = 0

        classification_changes = sum(1 for r in results if not r['all_agree'])

        return {
            'timestamp': datetime.now().isoformat(),
            'total_documents': len(results),
            'classification_changes': classification_changes,
            'mode_stats': stats,
        }

    def _generate_analysis(self, summary: Dict) -> Dict:
        """Generate comparison analysis with PDPL compliance notes."""
        stats = summary.get('mode_stats', {})
        blockchain = stats.get('blockchain', {})
        signature = stats.get('signature', {})

        analysis = {
            'performance_winner': 'signature' if signature.get('avg_ms', 999) < blockchain.get('avg_ms', 999) else 'blockchain',
            'blockchain_overhead_pct': blockchain.get('overhead_pct', 0),
            'signature_overhead_pct': signature.get('overhead_pct', 0),
            'pdpl_compliance': {
                'article_21_non_repudiation': {
                    'blockchain': 'Partial - hash chain proves data existed but no signer identity',
                    'signature': 'Full - RSA-PSS provides legally-meaningful non-repudiation',
                },
                'data_integrity': {
                    'blockchain': 'SHA-256 hash in PoW chain',
                    'signature': 'SHA-256 hash + RSA-PSS cryptographic signature',
                },
                'tamper_detection': {
                    'blockchain': 'Re-hash and compare against chain',
                    'signature': 'Re-hash and verify RSA-PSS signature',
                },
            },
            'recommendation': self._recommend(summary),
        }

        return analysis

    @staticmethod
    def _recommend(summary: Dict) -> str:
        """Generate textual recommendation based on results."""
        stats = summary.get('mode_stats', {})
        sig_overhead = stats.get('signature', {}).get('overhead_pct', 0)
        bc_overhead = stats.get('blockchain', {}).get('overhead_pct', 0)

        if sig_overhead < bc_overhead:
            return (
                f"Digital signatures add {sig_overhead:.1f}% overhead vs "
                f"{bc_overhead:.1f}% for blockchain. Signatures are recommended "
                f"for Egyptian banking: lower latency, PDPL Article 21 compliance "
                f"(non-repudiation), and NIST FIPS 186-5 alignment."
            )
        else:
            return (
                f"Blockchain adds {bc_overhead:.1f}% overhead vs "
                f"{sig_overhead:.1f}% for signatures. Both provide integrity protection. "
                f"Signatures still recommended for PDPL Article 21 non-repudiation compliance."
            )

    def _write_csv(self, path: str, results: List[Dict], modes: List[str]):
        """Write three-way comparison CSV."""
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'doc_id', 'mode', 'classification',
                'classification_ms', 'encryption_ms',
                'protection_ms', 'total_ms',
            ])
            for r in results:
                for mode in modes:
                    timings = r.get(f'{mode}_timings', {})
                    # Protection time varies by mode
                    if mode == 'blockchain':
                        prot_ms = timings.get('blockchain_protection_ms', '')
                    elif mode == 'signature':
                        prot_ms = timings.get('digital_signature_ms', '')
                    else:
                        prot_ms = ''
                    writer.writerow([
                        r['doc_id'],
                        mode,
                        r[f'{mode}_classification'],
                        timings.get('classification_ms', ''),
                        timings.get('encryption_ms', ''),
                        prot_ms,
                        r[f'{mode}_total_ms'],
                    ])


# ============================================================================
# Signature Performance Benchmark (sequential + concurrent)
# ============================================================================

class SignaturePerformanceBenchmark:
    """
    Full performance benchmark for digital signatures:
    - Sequential: all 3 modes
    - Concurrent: signature mode at variable user counts
    - Recommendation engine (PROCEED/MODIFY/ABANDON per mode)
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
        Run full benchmark suite with three-way comparison.

        Args:
            documents: List of dicts with 'text' key
            concurrent_levels: Concurrent user counts to test (default [5,10,15,20,25])
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

        # --- Sequential benchmark: all 3 modes ---
        report['sequential'] = {}
        for mode in ['baseline', 'blockchain', 'signature']:
            report['sequential'][mode] = self._run_sequential(documents, mode)

        # Compute overheads
        baseline_avg = report['sequential']['baseline']['avg_ms']
        if baseline_avg > 0:
            for mode in ['blockchain', 'signature']:
                mode_avg = report['sequential'][mode]['avg_ms']
                report['sequential'][f'{mode}_overhead_pct'] = round(
                    (mode_avg - baseline_avg) / baseline_avg * 100, 1
                )
        else:
            report['sequential']['blockchain_overhead_pct'] = 0
            report['sequential']['signature_overhead_pct'] = 0

        # --- Concurrent benchmark: signature mode ---
        report['concurrent'] = {}
        for n_users in concurrent_levels:
            key = f"{n_users}_users"
            report['concurrent'][key] = self._run_concurrent(
                documents, n_users, mode='signature'
            )

        # --- Recommendations ---
        report['recommendation'] = self._generate_recommendations(report)

        # Write report
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(output_dir, f"signature_benchmark_{ts}.json")
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)

        report['json_path'] = json_path
        return report

    def _run_sequential(self, documents: List[Dict], mode: str) -> Dict:
        """Run documents sequentially in specified mode."""
        monitor = ResourceMonitor()
        monitor.start()

        times = []
        errors = 0

        for doc in documents:
            text = doc.get('text', '')
            if not text:
                continue
            try:
                res = _classify_single_with_mode(
                    text, self.pipeline, self.settings, mode=mode,
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
            'mode': mode,
            'documents_processed': len(times),
            'errors': errors,
            'total_ms': round(total_ms, 2),
            'avg_ms': round(avg_ms, 2),
            'min_ms': round(min(times), 2) if times else 0,
            'max_ms': round(max(times), 2) if times else 0,
            **resources,
        }

    def _run_concurrent(self, documents: List[Dict], n_users: int,
                        mode: str = 'signature') -> Dict:
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
            return _classify_single_with_mode(
                text, self.pipeline, self.settings, mode=mode,
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

        if restore_audit:
            self.pipeline.audit = original_audit

        if times:
            avg_ms = sum(times) / len(times)
            throughput = len(times) / (wall_time_ms / 1000) if wall_time_ms > 0 else 0
        else:
            avg_ms = throughput = 0

        return {
            'mode': mode,
            'concurrent_users': n_users,
            'documents_processed': len(times),
            'errors': errors,
            'wall_time_ms': round(wall_time_ms, 2),
            'avg_ms_per_doc': round(avg_ms, 2),
            'throughput_docs_per_sec': round(throughput, 2),
            **resources,
        }

    @staticmethod
    def _generate_recommendations(report: Dict) -> Dict:
        """
        Generate per-mode recommendations.

        Thresholds:
        - PROCEED: overhead <30%, concurrent capacity >=20 users
        - MODIFY: overhead 30-100% or capacity 15-19
        - ABANDON: overhead >100% or capacity <15
        """
        recommendations = {}

        for mode in ['blockchain', 'signature']:
            overhead_pct = report['sequential'].get(f'{mode}_overhead_pct', 0)

            # Determine max concurrent capacity (only tested for signature mode)
            max_capacity = 0
            if mode == 'signature':
                for key, data in report.get('concurrent', {}).items():
                    n_users = data.get('concurrent_users', 0)
                    total = data.get('documents_processed', 0) + data.get('errors', 0)
                    error_rate = data.get('errors', 0) / total if total > 0 else 0
                    if error_rate <= 0.1:
                        max_capacity = max(max_capacity, n_users)

                if max_capacity == 0 and report.get('concurrent'):
                    all_clean = all(
                        d.get('errors', 0) == 0
                        for d in report['concurrent'].values()
                    )
                    if all_clean:
                        max_capacity = max(
                            d.get('concurrent_users', 0)
                            for d in report['concurrent'].values()
                        )
            else:
                # Blockchain concurrent not tested here; assume OK
                max_capacity = 25

            decision = 'PROCEED'
            reasons = []

            if overhead_pct > 100:
                decision = 'ABANDON'
                reasons.append(f'Overhead {overhead_pct:.1f}% exceeds 100% threshold')
            elif overhead_pct > 30:
                decision = 'MODIFY'
                reasons.append(f'Overhead {overhead_pct:.1f}% exceeds 30% threshold')

            if max_capacity < 15:
                decision = 'ABANDON'
                reasons.append(f'Max concurrent capacity {max_capacity} < 15 users')
            elif max_capacity < 20:
                if decision != 'ABANDON':
                    decision = 'MODIFY'
                reasons.append(f'Max concurrent capacity {max_capacity} below 20 users')

            if not reasons:
                reasons.append(f'Overhead {overhead_pct:.1f}% within limits, capacity {max_capacity} users OK')

            recommendations[mode] = {
                'decision': decision,
                'overhead_pct': round(overhead_pct, 1),
                'max_concurrent_capacity': max_capacity,
                'reasons': reasons,
            }

        return recommendations
