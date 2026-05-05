#!/usr/bin/env python3
import sys
import os
import json
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main_pipeline import DocumentPipeline, Config
from pdf_extractor import PDFExtractor, get_pdf_extractor
from blockchain_protection import DocumentProtectionChain
from benchmark import ABTestRunner, PerformanceBenchmark, load_benchmark_documents
from digital_signature import DocumentSignatureManager
from signature_benchmark import ThreeWayBenchmarkRunner, SignaturePerformanceBenchmark
from redaction import DocumentRedactor
from flag_manager import create_flag, resolve_flag, get_all_flagged, ciso_override, find_doc_by_flag_id
from pqc_encryption import PQCEncryption

# Accepted file types for document classification (PDF + images)
ALLOWED_DOCUMENT_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp')

def _is_pdf(filename):
    return filename and filename.lower().endswith('.pdf')

def _is_image(filename):
    if not filename:
        return False
    return any(filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp'))

def _extract_text_from_file(file, extractor):
    """Run PDF or image extraction; return (text, extraction_result_dict)."""
    raw = file.read()
    file.seek(0)
    if _is_pdf(file.filename):
        result = extractor.extract_from_bytes(raw)
    elif _is_image(file.filename):
        result = extractor.extract_from_image_bytes(raw, file.filename)
    else:
        raise ValueError('Unsupported file type. Use PDF or image (PNG, JPEG, etc.).')
    return result.get('text') or '', result

def _extraction_response_dict(extraction_result, text):
    """Build full extraction metadata for API response (all details)."""
    out = {
        'method': extraction_result.get('method', 'none'),
        'pages': extraction_result.get('pages', 0),
        'text_length': len(text),
        'success': extraction_result.get('success', False),
        'error': extraction_result.get('error'),
        'source': extraction_result.get('source', 'pdf'),
        'ocr_used': extraction_result.get('ocr_used', False),
        'language': extraction_result.get('language'),
        'dpi': extraction_result.get('dpi'),
        'tesseract_available': extraction_result.get('tesseract_available'),
        'tesseract_version': extraction_result.get('tesseract_version'),
        'notes': extraction_result.get('notes'),
    }
    if 'direct_text_length' in extraction_result:
        out['direct_text_length'] = extraction_result['direct_text_length']
    if 'ocr_text_length' in extraction_result:
        out['ocr_text_length'] = extraction_result['ocr_text_length']
    if 'pdf2image_available' in extraction_result:
        out['pdf2image_available'] = extraction_result['pdf2image_available']
    if 'pymupdf_available' in extraction_result:
        out['pymupdf_available'] = extraction_result['pymupdf_available']
    if 'ocr_engine' in extraction_result:
        out['ocr_engine'] = extraction_result['ocr_engine']
    if 'inference_time_seconds' in extraction_result:
        out['inference_time_seconds'] = extraction_result['inference_time_seconds']
    if 'image_mode' in extraction_result:
        out['image_mode'] = extraction_result['image_mode']
    if 'image_size' in extraction_result:
        out['image_size'] = extraction_result['image_size']
    if 'filename' in extraction_result:
        out['filename'] = extraction_result['filename']
    return out

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests (React runs on different port)

# Initialize pipeline once
pipeline = None

# Store current settings (in-memory, could be persisted to file)
current_settings = {
    'confidenceThreshold': 85,
    'hybridMode': 'conservative',
    'autoEscalate': True,
    'autoEncryptC2C3': True,
    'auditLogging': True,
    'enableBlockchainProtection': False,
    'enableDigitalSignature': False,
}

def get_pipeline():
    """Get or initialize the pipeline"""
    global pipeline
    if pipeline is None:
        pipeline = DocumentPipeline()
    return pipeline

def get_settings():
    """Get current settings"""
    global current_settings
    return current_settings


# ---------------------------------------------------------------------------
# Async OCR job queue
# Images processed with Qwen2.5-VL can take ~30-80s on CPU. We offload them
# to a background thread and let the client poll for the result via
# GET /api/ocr-job/<job_id> rather than blocking the HTTP request.
# ---------------------------------------------------------------------------
_ocr_jobs: dict = {}          # job_id -> {'status': str, 'result'|'error': ...}
_ocr_executor = ThreadPoolExecutor(max_workers=1)  # one Qwen job at a time on CPU


def _save_original_file(doc_id: str, file_bytes: bytes, filename: str):
    """Persist the original uploaded file so it can be watermarked from History later."""
    orig_dir = os.path.join(os.path.dirname(__file__), 'storage', 'original_files')
    os.makedirs(orig_dir, exist_ok=True)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    dest = os.path.join(orig_dir, f"{doc_id}.{ext}")
    with open(dest, 'wb') as f:
        f.write(file_bytes)


def _get_original_file(doc_id: str):
    """Return (file_bytes, filename) for a stored original file, or (None, None)."""
    orig_dir = os.path.join(os.path.dirname(__file__), 'storage', 'original_files')
    if not os.path.isdir(orig_dir):
        return None, None
    for fname in os.listdir(orig_dir):
        stem, _, ext = fname.rpartition('.')
        if stem == doc_id:
            with open(os.path.join(orig_dir, fname), 'rb') as f:
                return f.read(), fname
    return None, None


def _run_classify_pdf_job(job_id: str, file_bytes: bytes, filename: str,
                          doc_id: str, user_id, settings: dict, doc_department: str = None):
    """Background worker: extract text then run full classification pipeline."""
    try:
        _save_original_file(doc_id, file_bytes, filename)

        extractor = get_pdf_extractor()
        if _is_image(filename):
            extraction_result = extractor.extract_from_image_bytes(file_bytes, filename)
        else:
            extraction_result = extractor.extract_from_bytes(file_bytes)

        text = extraction_result.get('text') or ''

        if not extraction_result.get('success') or not text:
            _ocr_jobs[job_id] = {
                'status': 'error',
                'error': 'Could not extract text from document',
                'extraction_error': extraction_result.get('error'),
            }
            return

        p = get_pipeline()
        result = p.process_document(
            doc_id, text, user_id,
            confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
            hybrid_mode=settings.get('hybridMode', 'conservative'),
            auto_escalate=settings.get('autoEscalate', True),
            auto_encrypt=settings.get('autoEncryptC2C3', True),
            enable_blockchain_protection=settings.get('enableBlockchainProtection', False),
            enable_digital_signature=settings.get('enableDigitalSignature', False),
            doc_department=doc_department,
            original_filename=filename,
        )

        classification_data = result['stages']['classification']

        response_data = {
            'success': True,
            'doc_id': doc_id,
            'filename': filename,
            'classification': classification_data['classification'],
            'confidence': classification_data['confidence'],
            'confidence_factors': classification_data.get('confidence_factors', {}),
            'confidence_explanation': classification_data.get('confidence_explanation', ''),
            'confidence_formula': classification_data.get('confidence_formula', ''),
            'llm_raw_confidence': classification_data.get('llm_raw_confidence'),
            'method': classification_data['method'],
            'llm_classification': classification_data['llm_classification'],
            'rules_classification': classification_data['rules_classification'],
            'agreement': classification_data['agreement'],
            'reasoning': classification_data['reasoning'],
            'triggers': classification_data.get('triggers', []),
            'cde_detected': classification_data.get('cde_detected', []),
            'encrypted': result['stages']['encryption']['encrypted'],
            'storage_path': result['stages']['storage'].get('storage_path',
                            result['stages']['storage'].get('path', '')),
            'timestamp': result['timestamp'],
            'extraction': _extraction_response_dict(extraction_result, text),
            'status': 'ACTIVE',
        }
        if user_id:
            response_data['access'] = result['stages'].get('access', {})

        job_started = _ocr_jobs.get(job_id, {}).get('started_at', time.time())
        response_data['ocr_job_seconds'] = round(time.time() - job_started, 1)

        _ocr_jobs[job_id] = {'status': 'done', 'result': response_data}

    except Exception as e:
        import traceback
        traceback.print_exc()
        _ocr_jobs[job_id] = {'status': 'error', 'error': str(e)}

def update_settings(new_settings):
    """Update settings"""
    global current_settings
    current_settings.update(new_settings)
    return current_settings


def _enrich_document_metadata(doc_data):
    """Fill in missing classification metadata for legacy stored docs (so UI can show LLM/Rules/triggers)."""
    meta = dict(doc_data.get('metadata', {}))
    classification = doc_data.get('classification')
    method = meta.get('classification_method')
    # Rules result: when rules overrode or escalated, rules classification is the final classification
    if meta.get('rules_classification') is None and method in ('RULES_OVERRIDE', 'RULES_ESCALATED') and classification:
        meta['rules_classification'] = classification
    # LLM result: when agreement, both are same; when AI/LLM decided, LLM gave the final classification
    if meta.get('llm_classification') is None and classification:
        if method == 'AGREEMENT':
            meta['llm_classification'] = classification
        elif method in ('AI_DECISION', 'LLAMA_ONLY', 'LLM_TRUSTED', 'LLM_CONFIDENT', 'LLM_HIGHER', 'LLM_NO_ESCALATE'):
            meta['llm_classification'] = classification
    if meta.get('agreement') is None:
        llm, rules = meta.get('llm_classification'), meta.get('rules_classification')
        if llm is not None and rules is not None:
            meta['agreement'] = (llm == rules)
        elif method == 'AGREEMENT':
            meta['agreement'] = True
    return meta


def get_required_level(classification: str, action: str) -> dict:
    """Get the required access level for a classification and action"""
    requirements = {
        'C0': {'view': 1, 'download': 1, 'print': 1},
        'C1': {'view': 2, 'download': 2, 'print': 2},
        'C2': {'view': 3, 'download': 3, 'print': 5},
        'C3': {'view': 3, 'download': 3, 'print': 5}
    }
    level_names = {
        1: 'Public User',
        2: 'Employee',
        3: 'Manager',
        4: 'Senior Manager',
        5: 'Administrator'
    }
    level = requirements.get(classification, {}).get(action, 5)
    return {
        'level': level,
        'role': level_names.get(level, 'Unknown')
    }


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """API root - redirect to health check"""
    return jsonify({
        'message': 'Document Classification API',
        'status': 'running',
        'frontend': 'Use React dashboard on port 5173'
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Document Classification API is running'
    })


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update classification settings"""
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'settings': get_settings()
        })
    else:  # POST
        try:
            data = request.get_json()
            if data:
                updated = update_settings(data)
                return jsonify({
                    'success': True,
                    'settings': updated
                })
            return jsonify({'error': 'No settings provided'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/classify', methods=['POST'])
def classify_document():
    """
    Classify a single document

    Request body:
    {
        "doc_id": "DOC_001",
        "text": "Document content here...",
        "user_id": "U002"  (optional),
        "true_label": "C3"  (optional - ground truth for evaluation),
        "settings": { ... }  (optional - override settings for this request)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        doc_id = data.get('doc_id', f'DOC_{os.urandom(4).hex()}')
        text = data.get('text', '')
        user_id = data.get('user_id')
        true_label = data.get('true_label')  # Ground truth label for evaluation

        # Get settings - use request settings if provided, else use global settings
        request_settings = data.get('settings', {})
        settings = {**get_settings(), **request_settings}

        if not text:
            return jsonify({'error': 'Document text is required'}), 400

        # Process document with settings
        p = get_pipeline()
        result = p.process_document(
            doc_id,
            text,
            user_id,
            confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
            hybrid_mode=settings.get('hybridMode', 'conservative'),
            auto_escalate=settings.get('autoEscalate', True),
            auto_encrypt=settings.get('autoEncryptC2C3', True),
            true_label=true_label,
            enable_blockchain_protection=settings.get('enableBlockchainProtection', False),
            enable_digital_signature=settings.get('enableDigitalSignature', False),
        )

        # Extract key information for response
        classification_data = result['stages']['classification']
        response = {
            'success': True,
            'doc_id': doc_id,
            'classification': classification_data['classification'],
            'confidence': classification_data['confidence'],
            'confidence_factors': classification_data.get('confidence_factors', {}),
            'confidence_explanation': classification_data.get('confidence_explanation', ''),
            'confidence_formula': classification_data.get('confidence_formula', ''),
            'llm_raw_confidence': classification_data.get('llm_raw_confidence'),
            'method': classification_data['method'],
            'llm_classification': classification_data['llm_classification'],
            'rules_classification': classification_data['rules_classification'],
            'agreement': classification_data['agreement'],
            'reasoning': classification_data['reasoning'],
            'triggers': classification_data.get('triggers', []),
            'cde_detected': classification_data.get('cde_detected', []),
            'encrypted': result['stages']['encryption']['encrypted'],
            'storage_path': result['stages']['storage']['path'],
            'timestamp': result['timestamp']
        }

        # Add true_label if provided
        if true_label:
            response['true_label'] = true_label
            response['correct'] = result['stages']['classification']['classification'] == true_label

        # Add access info if user_id was provided
        if 'access' in result['stages']:
            response['access'] = result['stages']['access']

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/classify/pdf', methods=['POST'])
def classify_pdf():
    """
    Classify a PDF or image document (with automatic text extraction and OCR).

    Accepts:
    - multipart/form-data with 'file' field: PDF or image (PNG, JPEG, GIF, BMP, TIFF, WebP)
    - Optional 'user_id', 'doc_id'

    Returns:
    - Same response as /api/classify plus full extraction metadata
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided. Use multipart/form-data with "file" field'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not any(file.filename.lower().endswith(ext) for ext in ALLOWED_DOCUMENT_EXTENSIONS):
            return jsonify({
                'error': 'Unsupported file type. Use PDF or image (PNG, JPEG, GIF, BMP, TIFF, WebP).'
            }), 400

        user_id = request.form.get('user_id')
        doc_id = request.form.get('doc_id', f'DOC_{os.urandom(4).hex()}')
        settings = get_settings()

        # Resolve department from logged-in user
        doc_department = None
        if user_id:
            p0 = get_pipeline()
            u0 = p0.rbac.get_user(user_id)
            if u0:
                doc_department = u0.department if u0.department not in ('All', 'None', None) else None

        # Image files use Qwen2.5-VL OCR which can take ~30-80s on CPU.
        # Offload to a background thread and return a job_id for polling.
        if _is_image(file.filename):
            file_bytes = file.read()
            job_id = str(uuid.uuid4())
            _ocr_jobs[job_id] = {'status': 'processing', 'started_at': time.time()}
            _ocr_executor.submit(
                _run_classify_pdf_job,
                job_id, file_bytes, file.filename, doc_id, user_id, settings, doc_department
            )
            return jsonify({'status': 'processing', 'job_id': job_id, 'doc_id': doc_id,
                            'started_at': _ocr_jobs[job_id]['started_at']})

        # PDF and other files: synchronous path (text extraction is fast)
        file_bytes = file.read()
        file.seek(0)
        _save_original_file(doc_id, file_bytes, file.filename)

        extractor = get_pdf_extractor()
        try:
            text, extraction_result = _extract_text_from_file(file, extractor)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        if not extraction_result.get('success') or not text:
            return jsonify({
                'error': 'Could not extract text from document',
                'extraction_method': extraction_result.get('method'),
                'extraction_error': extraction_result.get('error'),
            }), 400

        p = get_pipeline()
        result = p.process_document(
            doc_id,
            text,
            user_id,
            confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
            hybrid_mode=settings.get('hybridMode', 'conservative'),
            auto_escalate=settings.get('autoEscalate', True),
            auto_encrypt=settings.get('autoEncryptC2C3', True),
            enable_blockchain_protection=settings.get('enableBlockchainProtection', False),
            enable_digital_signature=settings.get('enableDigitalSignature', False),
            doc_department=doc_department,
            original_filename=file.filename,
        )

        # Read stored status
        stored_status = 'PENDING_REVIEW'
        stored_route = 'COMPLIANCE'
        try:
            _sp = result['stages']['storage'].get('path', '')
            if _sp and os.path.exists(_sp):
                with open(_sp) as _sf:
                    _sd = json.load(_sf)
                stored_status = _sd.get('status', 'PENDING_REVIEW')
                stored_route = _sd.get('verification_route', 'COMPLIANCE')
        except Exception:
            pass

        classification_data = result['stages']['classification']
        response = {
            'success': True,
            'doc_id': doc_id,
            'filename': file.filename,
            'classification': classification_data['classification'],
            'confidence': classification_data['confidence'],
            'confidence_factors': classification_data.get('confidence_factors', {}),
            'confidence_explanation': classification_data.get('confidence_explanation', ''),
            'confidence_formula': classification_data.get('confidence_formula', ''),
            'llm_raw_confidence': classification_data.get('llm_raw_confidence'),
            'method': classification_data['method'],
            'llm_classification': classification_data['llm_classification'],
            'rules_classification': classification_data['rules_classification'],
            'agreement': classification_data['agreement'],
            'reasoning': classification_data['reasoning'],
            'triggers': classification_data.get('triggers', []),
            'cde_detected': classification_data.get('cde_detected', []),
            'encrypted': result['stages']['encryption']['encrypted'],
            'storage_path': result['stages']['storage'].get('storage_path', result['stages']['storage'].get('path', '')),
            'timestamp': result['timestamp'],
            'extraction': _extraction_response_dict(extraction_result, text),
            'status': stored_status,
            'verification_route': stored_route,
        }
        if user_id:
            response['access'] = result['stages']['access']
        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr-job/<job_id>', methods=['GET'])
def get_ocr_job(job_id):
    """Poll the status of an async OCR+classification job submitted by /api/classify/pdf."""
    job = _ocr_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    if job['status'] == 'processing':
        elapsed = round(time.time() - job.get('started_at', time.time()), 1)
        return jsonify({'status': 'processing', 'elapsed_seconds': elapsed})
    if job['status'] == 'error':
        return jsonify({'status': 'error', 'error': job.get('error', 'Unknown error')}), 500
    # Done — return full classification result and clean up
    result = dict(job['result'])
    _ocr_jobs.pop(job_id, None)
    return jsonify(result)


@app.route('/api/classify/steps', methods=['POST'])
def classify_document_steps():
    """
    Classify a text document and return full pipeline steps for UI visualization.
    Request body: { "doc_id", "text", "user_id" (optional), "settings" (optional) }
    Returns: { success, doc_id, extraction: null, pipeline_result: { timestamp, stages } }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        doc_id = data.get('doc_id', f'DOC_{os.urandom(4).hex()}')
        text = data.get('text', '')
        user_id = data.get('user_id')
        request_settings = data.get('settings', {})
        settings = {**get_settings(), **request_settings}

        if not text:
            return jsonify({'error': 'Document text is required'}), 400

        p = get_pipeline()
        result = p.process_document(
            doc_id,
            text,
            user_id,
            confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
            hybrid_mode=settings.get('hybridMode', 'conservative'),
            auto_escalate=settings.get('autoEscalate', True),
            auto_encrypt=settings.get('autoEncryptC2C3', True),
            enable_blockchain_protection=settings.get('enableBlockchainProtection', False),
            enable_digital_signature=settings.get('enableDigitalSignature', False),
        )

        return jsonify({
            'success': True,
            'doc_id': doc_id,
            'extraction': None,
            'pipeline_result': result,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/classify/pdf/steps', methods=['POST'])
def classify_pdf_steps():
    """
    Classify a PDF or image and return full pipeline steps including detailed extraction for UI.
    Accepts: multipart/form-data with 'file' (PDF or image), optional 'user_id', 'doc_id'
    Returns: { success, doc_id, extraction: { full details }, pipeline_result: { timestamp, stages } }
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided. Use multipart/form-data with "file" field'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not any(file.filename.lower().endswith(ext) for ext in ALLOWED_DOCUMENT_EXTENSIONS):
            return jsonify({
                'error': 'Unsupported file type. Use PDF or image (PNG, JPEG, GIF, BMP, TIFF, WebP).'
            }), 400

        user_id = request.form.get('user_id')
        doc_id = request.form.get('doc_id', f'DOC_{os.urandom(4).hex()}')
        true_label = request.form.get('true_label') or None

        file_bytes_steps = file.read()
        file.seek(0)
        _save_original_file(doc_id, file_bytes_steps, file.filename)

        extractor = get_pdf_extractor()
        try:
            text, extraction_result = _extract_text_from_file(file, extractor)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        if not extraction_result.get('success') or not text:
            return jsonify({
                'error': 'Could not extract text from document',
                'extraction_method': extraction_result.get('method'),
                'extraction_error': extraction_result.get('error'),
            }), 400

        settings = get_settings()
        p = get_pipeline()
        result = p.process_document(
            doc_id,
            text,
            user_id,
            confidence_threshold=settings.get('confidenceThreshold', 85) / 100,
            hybrid_mode=settings.get('hybridMode', 'conservative'),
            auto_escalate=settings.get('autoEscalate', True),
            auto_encrypt=settings.get('autoEncryptC2C3', True),
            true_label=true_label,
            enable_blockchain_protection=settings.get('enableBlockchainProtection', False),
            enable_digital_signature=settings.get('enableDigitalSignature', False),
        )

        return jsonify({
            'success': True,
            'doc_id': doc_id,
            'filename': file.filename,
            'extraction': _extraction_response_dict(extraction_result, text),
            'pipeline_result': result,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/classify/batch', methods=['POST'])
def classify_batch():
    """
    Classify multiple documents

    Request body:
    {
        "documents": [
            {"doc_id": "DOC_001", "text": "..."},
            {"doc_id": "DOC_002", "text": "..."}
        ]
    }
    """
    try:
        data = request.get_json()

        if not data or 'documents' not in data:
            return jsonify({'error': 'Documents array is required'}), 400

        documents = data['documents']
        p = get_pipeline()
        settings = get_settings()

        results = []
        for doc in documents:
            doc_id = doc.get('doc_id', f'DOC_{os.urandom(4).hex()}')
            text = doc.get('text', '')
            user_id = doc.get('user_id')

            if text:
                result = p.process_document(
                    doc_id, text, user_id,
                    enable_blockchain_protection=settings.get('enableBlockchainProtection', False),
                    enable_digital_signature=settings.get('enableDigitalSignature', False),
                )
                results.append({
                    'doc_id': doc_id,
                    'classification': result['stages']['classification']['classification'],
                    'confidence': result['stages']['classification']['confidence'],
                    'method': result['stages']['classification']['method'],
                    'encrypted': result['stages']['encryption']['encrypted']
                })

        return jsonify({
            'success': True,
            'processed': len(results),
            'results': results
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get pipeline statistics"""
    try:
        p = get_pipeline()
        stats = p.get_statistics()
        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/users', methods=['GET'])
def get_users():
    """Get list of available users (without passwords)"""
    try:
        p = get_pipeline()
        users = []
        for user in p.rbac.users.values():
            users.append({
                'user_id': user.user_id,
                'username': user.username,
                'name': user.name,
                'role': user.role,
                'access_level': user.access_level,
                'department': user.department
            })
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user with username + password. Returns user info (no token — demo)."""
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not username or not password:
            return jsonify({'success': False, 'error': 'username and password required'}), 400
        p = get_pipeline()
        user = p.rbac.authenticate(username, password)
        if not user:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
        p.audit.log_event('USER_LOGIN', {
            'user_id': user.user_id,
            'user_name': user.name,
            'user_level': user.access_level,
            'role': user.role,
            'department': user.department,
        })
        return jsonify({
            'success': True,
            'user': {
                'user_id': user.user_id,
                'username': user.username,
                'name': user.name,
                'role': user.role,
                'access_level': user.access_level,
                'department': user.department,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents', methods=['GET'])
def get_stored_documents():
    """Get list of stored documents"""
    try:
        documents = []
        storage_dir = Config.STORAGE_DIR

        # Reasoning may contain PII — visible to CISO (L5) and DPO only
        requesting_user_id = request.args.get('user_id')
        show_reasoning = False
        if requesting_user_id:
            try:
                p = get_pipeline()
                req_user = p.rbac.get_user(requesting_user_id)
                show_reasoning = req_user and (
                    req_user.access_level >= 5 or req_user.role == 'DPO'
                )
            except Exception:
                pass

        # Load protection chain once for batch integrity checks
        protection_chain = None
        try:
            protection_chain = DocumentProtectionChain(storage_dir=Config.STORAGE_DIR)
        except Exception:
            pass

        if os.path.exists(storage_dir):
            for filename in os.listdir(storage_dir):
                if not filename.endswith('.json'):
                    continue
                filepath = os.path.join(storage_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        doc_data = json.load(f)
                    doc_id = doc_data.get('doc_id')
                    if not doc_id:
                        continue  # skip entries without doc_id so UI can render
                    meta = _enrich_document_metadata(doc_data)

                    # Integrity check (silent — errors don't block listing)
                    integrity_check = None
                    if protection_chain:
                        try:
                            integrity_check = protection_chain.verify_document(doc_id)
                        except Exception:
                            pass

                    documents.append({
                        'doc_id': doc_id,
                        'classification': doc_data.get('final_classification') or doc_data.get('classification'),
                        'timestamp': doc_data.get('timestamp'),
                        'encrypted': doc_data.get('encrypted_data') is not None,
                        'text_length': meta.get('text_length', 0),
                        'method': meta.get('classification_method'),
                        'reasoning': meta.get('reasoning') if show_reasoning else None,
                        'ai_reasoning': doc_data.get('ai_reasoning') if show_reasoning else None,
                        'confidence': meta.get('confidence'),
                        'llm_classification': meta.get('llm_classification'),
                        'rules_classification': meta.get('rules_classification'),
                        'triggers': meta.get('triggers', []),
                        # New fields
                        'department': doc_data.get('department'),
                        'status': 'ACTIVE',
                        'document_type': doc_data.get('document_type', 'General Banking Document'),
                        'ai_classification': doc_data.get('ai_classification'),
                        'ai_confidence': doc_data.get('ai_confidence'),
                        'uploaded_by': doc_data.get('uploaded_by'),
                        'original_filename': doc_data.get('original_filename'),
                        'cde_detected': doc_data.get('cde_detected', []),
                        'integrity_check': integrity_check,
                        'flag': doc_data.get('flag'),
                    })
                except (json.JSONDecodeError, IOError):
                    continue  # skip corrupted or unreadable files

        return jsonify({
            'success': True,
            'count': len(documents),
            'documents': documents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HUMAN REVIEW / FLAG ENDPOINTS
# ============================================================================

@app.route('/api/documents/<doc_id>/flag', methods=['POST'])
def flag_document_endpoint(doc_id):
    """
    Flag a document as potentially misclassified.
    Requires minimum Level 2 access. Level 1 (Viewer) cannot flag.
    Body: { flagged_by_id, flagged_by_name, comment, suggested_classification? }
    """
    try:
        body = request.get_json() or {}
        flagged_by_id   = (body.get('flagged_by_id') or 'anonymous').strip()
        flagged_by_name = (body.get('flagged_by_name') or 'Anonymous').strip()
        comment         = (body.get('comment') or '').strip()
        suggested       = body.get('suggested_classification') or None

        # Enforce minimum Level 2 — Viewers (L1) cannot flag documents
        p = get_pipeline()
        requesting_user = p.rbac.get_user(flagged_by_id)
        if requesting_user is None or requesting_user.access_level < 2:
            return jsonify({
                'success': False,
                'error': 'Access denied. Flagging requires minimum Level 2 access.'
            }), 403

        if not comment:
            return jsonify({'success': False, 'error': 'comment is required'}), 400

        flag = create_flag(
            doc_id=doc_id,
            flagged_by_id=flagged_by_id,
            flagged_by_name=flagged_by_name,
            comment=comment,
            suggested_classification=suggested,
            storage_dir=Config.STORAGE_DIR,
        )

        # Re-protect after flag write so hash stays current
        try:
            DocumentProtectionChain(storage_dir=Config.STORAGE_DIR).protect_document_from_file(
                doc_id, user_id=flagged_by_id
            )
        except Exception:
            pass

        return jsonify({'success': True, 'flag': flag})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<doc_id>/flag/resolve', methods=['POST'])
def resolve_flag_endpoint(doc_id):
    """
    DPO resolves a pending flag (DPO role only — PDPL compliance function).
    Body: { resolved_by_id, resolved_by_name, action, comment, override_classification? }
    action: 'MAINTAIN' | 'OVERRIDE'
    """
    try:
        body = request.get_json() or {}
        resolved_by_id   = (body.get('resolved_by_id') or 'unknown').strip()
        resolved_by_name = (body.get('resolved_by_name') or 'DPO').strip()
        action           = (body.get('action') or '').strip().upper()
        comment          = (body.get('comment') or '').strip()
        override         = body.get('override_classification') or None

        # DPO-only: CISO and all other roles are forbidden from the flag queue
        p = get_pipeline()
        acting_user = p.rbac.get_user(resolved_by_id)
        if acting_user is None or acting_user.role != 'DPO':
            return jsonify({
                'success': False,
                'error': 'Access denied. Only the DPO can resolve flags.'
            }), 403

        if not action:
            return jsonify({'success': False, 'error': 'action is required (MAINTAIN or OVERRIDE)'}), 400
        if not comment:
            return jsonify({'success': False, 'error': 'comment is required'}), 400

        # Capture old classification before resolve_flag writes
        doc_path_rf = os.path.join(Config.STORAGE_DIR, f'{doc_id}.json')
        old_class_rf = None
        try:
            with open(doc_path_rf, 'r', encoding='utf-8') as _f:
                _pre = json.load(_f)
            old_class_rf = _pre.get('final_classification') or _pre.get('classification')
        except Exception:
            pass

        flag = resolve_flag(
            doc_id=doc_id,
            resolved_by_id=resolved_by_id,
            resolved_by_name=resolved_by_name,
            action=action,
            comment=comment,
            override_classification=override,
            storage_dir=Config.STORAGE_DIR,
        )

        # Sync encryption if DPO overrode the classification across the plaintext/encrypted boundary
        if action == 'OVERRIDE' and override and old_class_rf:
            try:
                old_needs_enc = old_class_rf in ('C2', 'C3')
                new_needs_enc = override in ('C2', 'C3')
                if old_needs_enc != new_needs_enc:
                    with open(doc_path_rf, 'r', encoding='utf-8') as _f:
                        _doc = json.load(_f)
                    _pqc = PQCEncryption()
                    if new_needs_enc:
                        _pt = _doc.get('original_text') or ''
                        if _pt:
                            _enc = _pqc.encrypt(_pt, override)
                            if _enc.get('encrypted'):
                                _doc['encrypted_data'] = {
                                    'encrypted': True,
                                    'algorithm': _enc.get('algorithm', 'Kyber-768 + AES-256-GCM'),
                                    'ciphertext': _enc['ciphertext'],
                                    'key_id': _enc['key_id'],
                                    'encapsulated_key': _enc['encapsulated_key'],
                                    'nonce': _enc['nonce'],
                                    'shared_secret': _enc.get('shared_secret'),
                                }
                                _doc['original_text'] = None
                    else:
                        _ed = _doc.get('encrypted_data')
                        if _ed and _ed.get('encrypted'):
                            try:
                                _pt = _pqc.decrypt(
                                    _ed['ciphertext'], _ed['key_id'],
                                    _ed['encapsulated_key'], _ed['nonce'],
                                    _ed.get('shared_secret'),
                                )
                                _doc['original_text'] = _pt
                                _doc['encrypted_data'] = None
                            except Exception:
                                pass
                    with open(doc_path_rf, 'w', encoding='utf-8') as _f:
                        json.dump(_doc, _f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        # Audit log the DPO action to blockchain
        try:
            p.audit.log_event('FLAG_' + action, {
                'document_id': doc_id,
                'flag_id': flag.get('flag_id'),
                'acting_user': resolved_by_id,
                'acting_user_name': resolved_by_name,
                'action': action,
                'comment': comment,
                'override_classification': override if action == 'OVERRIDE' else None,
                'timestamp': flag.get('resolved_at'),
            })
        except Exception:
            pass

        # Re-protect after flag resolve so hash stays current
        try:
            DocumentProtectionChain(storage_dir=Config.STORAGE_DIR).protect_document_from_file(
                doc_id, user_id=resolved_by_id
            )
        except Exception:
            pass

        return jsonify({'success': True, 'flag': flag})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<doc_id>/override', methods=['POST'])
def ciso_override_endpoint(doc_id):
    """
    CISO directly overrides the classification of any document.
    Requires mandatory reasoning which is stored for future LLM improvement.
    Body: { overridden_by_id, overridden_by_name, new_classification, reasoning }
    """
    try:
        body = request.get_json() or {}
        overridden_by_id   = (body.get('overridden_by_id') or 'unknown').strip()
        overridden_by_name = (body.get('overridden_by_name') or 'CISO').strip()
        new_classification = (body.get('new_classification') or '').strip().upper()
        reasoning          = (body.get('reasoning') or '').strip()

        if not new_classification:
            return jsonify({'success': False, 'error': 'new_classification is required'}), 400
        if not reasoning:
            return jsonify({'success': False, 'error': 'reasoning is required'}), 400

        # Load the document BEFORE the override so we know the old classification
        doc_path = os.path.join(Config.STORAGE_DIR, f'{doc_id}.json')
        if not os.path.exists(doc_path):
            return jsonify({'success': False, 'error': f"Document '{doc_id}' not found"}), 404
        with open(doc_path, 'r', encoding='utf-8') as f:
            doc_before = json.load(f)
        old_classification = doc_before.get('final_classification') or doc_before.get('classification', '')

        override = ciso_override(
            doc_id=doc_id,
            overridden_by_id=overridden_by_id,
            overridden_by_name=overridden_by_name,
            new_classification=new_classification,
            reasoning=reasoning,
            storage_dir=Config.STORAGE_DIR,
        )

        # ── Sync encryption state to the new classification ──────────────────
        # C0/C1 are plaintext; C2/C3 are PQC-encrypted.
        # When the classification crosses that boundary, add or remove encryption.
        try:
            old_needs_enc = old_classification in ('C2', 'C3')
            new_needs_enc = new_classification in ('C2', 'C3')

            if old_needs_enc != new_needs_enc:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    doc = json.load(f)

                pqc = PQCEncryption()

                if new_needs_enc:
                    # Upgrading C0/C1 → C2/C3: encrypt the stored plaintext
                    plaintext = doc.get('original_text') or ''
                    if plaintext:
                        enc = pqc.encrypt(plaintext, new_classification)
                        if enc.get('encrypted'):
                            doc['encrypted_data'] = {
                                'encrypted': True,
                                'algorithm': enc.get('algorithm', 'Kyber-768 + AES-256-GCM'),
                                'ciphertext': enc['ciphertext'],
                                'key_id': enc['key_id'],
                                'encapsulated_key': enc['encapsulated_key'],
                                'nonce': enc['nonce'],
                                'shared_secret': enc.get('shared_secret'),
                            }
                            doc['original_text'] = None
                else:
                    # Downgrading C2/C3 → C0/C1: decrypt and restore plaintext
                    enc_data = doc.get('encrypted_data')
                    if enc_data and enc_data.get('encrypted'):
                        try:
                            plaintext = pqc.decrypt(
                                enc_data['ciphertext'],
                                enc_data['key_id'],
                                enc_data['encapsulated_key'],
                                enc_data['nonce'],
                                enc_data.get('shared_secret'),
                            )
                            doc['original_text'] = plaintext
                            doc['encrypted_data'] = None
                        except Exception:
                            pass  # Leave encryption as-is if decrypt fails

                with open(doc_path, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, indent=2, ensure_ascii=False)

            elif new_needs_enc and old_classification != new_classification:
                # Both are encrypted tiers (C2↔C3): update classification tag inside encrypted_data
                with open(doc_path, 'r', encoding='utf-8') as f:
                    doc = json.load(f)
                if doc.get('encrypted_data'):
                    doc['encrypted_data']['classification'] = new_classification
                    with open(doc_path, 'w', encoding='utf-8') as f:
                        json.dump(doc, f, indent=2, ensure_ascii=False)

        except Exception:
            pass  # Non-fatal — classification is already updated; encryption sync is best-effort

        # Re-protect the document after all writes so the protection chain
        # reflects the current hash — prevents false TAMPERED badges.
        try:
            DocumentProtectionChain(storage_dir=Config.STORAGE_DIR).protect_document_from_file(
                doc_id, user_id=overridden_by_id
            )
        except Exception:
            pass

        return jsonify({'success': True, 'override': override})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/flags/<flag_id>/approve', methods=['POST'])
def dpo_approve_flag(flag_id):
    """
    DPO approves an existing classification (MAINTAIN action).
    DPO only. Body: { dpo_id, dpo_name, comment }
    Logged to blockchain audit trail.
    """
    try:
        body = request.get_json() or {}
        dpo_id   = (body.get('dpo_id') or '').strip()
        dpo_name = (body.get('dpo_name') or 'DPO').strip()
        comment  = (body.get('comment') or '').strip()

        p = get_pipeline()
        acting_user = p.rbac.get_user(dpo_id)
        if acting_user is None or acting_user.role != 'DPO':
            return jsonify({'success': False, 'error': 'Access denied. Only the DPO can approve flags.'}), 403
        if not comment:
            return jsonify({'success': False, 'error': 'comment is required'}), 400

        doc_id = find_doc_by_flag_id(flag_id, Config.STORAGE_DIR)
        if not doc_id:
            return jsonify({'success': False, 'error': f"Flag '{flag_id}' not found"}), 404

        flag = resolve_flag(
            doc_id=doc_id,
            resolved_by_id=dpo_id,
            resolved_by_name=dpo_name,
            action='MAINTAIN',
            comment=comment,
            storage_dir=Config.STORAGE_DIR,
        )
        p.audit.log_event('FLAG_APPROVED', {
            'document_id': doc_id,
            'flag_id': flag_id,
            'acting_user': dpo_id,
            'acting_user_name': dpo_name,
            'action': 'APPROVED',
            'comment': comment,
            'timestamp': flag.get('resolved_at'),
        })
        DocumentProtectionChain(storage_dir=Config.STORAGE_DIR).protect_document_from_file(
            doc_id, user_id=dpo_id
        )
        return jsonify({'success': True, 'flag': flag})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/flags/<flag_id>/override', methods=['POST'])
def dpo_override_flag(flag_id):
    """
    DPO overrides classification for a flagged document.
    DPO only. Mandatory comment required (400 if missing).
    Body: { dpo_id, dpo_name, new_classification, comment }
    Logged to blockchain audit trail.
    """
    try:
        body = request.get_json() or {}
        dpo_id          = (body.get('dpo_id') or '').strip()
        dpo_name        = (body.get('dpo_name') or 'DPO').strip()
        new_cls         = (body.get('new_classification') or '').strip().upper()
        comment         = (body.get('comment') or '').strip()

        p = get_pipeline()
        acting_user = p.rbac.get_user(dpo_id)
        if acting_user is None or acting_user.role != 'DPO':
            return jsonify({'success': False, 'error': 'Access denied. Only the DPO can override flags.'}), 403
        if not new_cls:
            return jsonify({'success': False, 'error': 'new_classification is required'}), 400
        if not comment:
            return jsonify({'success': False, 'error': 'comment is required'}), 400

        doc_id = find_doc_by_flag_id(flag_id, Config.STORAGE_DIR)
        if not doc_id:
            return jsonify({'success': False, 'error': f"Flag '{flag_id}' not found"}), 404

        flag = resolve_flag(
            doc_id=doc_id,
            resolved_by_id=dpo_id,
            resolved_by_name=dpo_name,
            action='OVERRIDE',
            comment=comment,
            override_classification=new_cls,
            storage_dir=Config.STORAGE_DIR,
        )
        p.audit.log_event('FLAG_OVERRIDDEN', {
            'document_id': doc_id,
            'flag_id': flag_id,
            'acting_user': dpo_id,
            'acting_user_name': dpo_name,
            'action': 'OVERRIDDEN',
            'new_classification': new_cls,
            'comment': comment,
            'timestamp': flag.get('resolved_at'),
        })
        DocumentProtectionChain(storage_dir=Config.STORAGE_DIR).protect_document_from_file(
            doc_id, user_id=dpo_id
        )
        return jsonify({'success': True, 'flag': flag})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/flagged-documents', methods=['GET'])
@app.route('/api/flags/queue', methods=['GET'])
def get_flagged_documents_endpoint():
    """
    Return all flagged documents. DPO-only (PDPL Art. 4).
    CISO has no access — flag review is a PDPL compliance function, not security governance.
    Query param: ?status=PENDING|RESOLVED (omit for all), ?user_id=<id>
    """
    try:
        requesting_user_id = request.args.get('user_id') or None
        p = get_pipeline()
        if requesting_user_id:
            req_user = p.rbac.get_user(requesting_user_id)
            if req_user is None:
                return jsonify({'success': False, 'error': 'User not found'}), 403
            if req_user.role != 'DPO':
                return jsonify({
                    'success': False,
                    'error': 'Access denied. Flag review queue is restricted to the DPO.'
                }), 403
        # No user_id provided — anonymous call is also denied for this sensitive endpoint
        else:
            return jsonify({'success': False, 'error': 'user_id is required'}), 403

        status_filter = request.args.get('status') or None
        if status_filter and status_filter not in ('PENDING', 'RESOLVED'):
            return jsonify({'success': False, 'error': 'status must be PENDING or RESOLVED'}), 400
        results = get_all_flagged(status_filter=status_filter, storage_dir=Config.STORAGE_DIR)
        return jsonify({'success': True, 'count': len(results), 'documents': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    """Get audit trail logs. CISO sees all; other users see only their own events."""
    try:
        p = get_pipeline()
        requesting_user_id = request.args.get('user_id') or None

        # Determine if requester is CISO (full access) or regular user (own events only)
        is_ciso = False
        if requesting_user_id:
            req_user = p.rbac.get_user(requesting_user_id)
            if req_user and req_user.access_level >= 5:
                is_ciso = True

        all_logs = p.audit.logs[-50:]
        logs = []
        for log in all_logs:
            # Non-CISO users only see events where they are the actor
            if not is_ciso and requesting_user_id:
                data = log.data if isinstance(log.data, dict) else {}
                actor = data.get('user_id') or data.get('acting_user') or data.get('uploaded_by')
                if actor != requesting_user_id:
                    continue
            logs.append({
                'event_id': log.log_id,
                'event_type': log.event_type,
                'timestamp': log.timestamp,
                'data': log.data
            })

        return jsonify({
            'success': True,
            'count': len(logs),
            'chain_valid': p.audit.verify_chain_integrity()['valid'],
            'logs': logs
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/blockchain-audit', methods=['GET'])
def get_blockchain_audit():
    """
    Get blockchain-based audit trail
    Only accessible by Level 5 users (verified client-side and server-side)
    """
    try:
        # Check user access level
        user_id = request.args.get('user_id')
        p = get_pipeline()

        if user_id:
            user = p.rbac.get_user(user_id)
            if not user or user.access_level < 5:
                return jsonify({
                    'success': False,
                    'error': 'Access Denied',
                    'message': 'Blockchain audit trail is only accessible to Level 5 administrators.'
                }), 403

        # Get audit blockchain status
        status = p.audit.get_blockchain_status()

        # Get full audit blockchain
        blockchain = p.audit.get_blockchain()

        # Verify audit chain integrity
        verification = p.audit.verify_blockchain()

        # Get legacy chain integrity too
        legacy_verification = p.audit.verify_chain_integrity()

        # Get protection chain status (separate blockchain)
        protection_chain = DocumentProtectionChain(
            storage_dir=Config.STORAGE_DIR,
        )
        protection_status = protection_chain.get_chain_status()
        protection_verification = protection_chain.verify_chain()

        return jsonify({
            'success': True,
            'blockchain': {
                'status': status,
                'verification': verification,
                'blocks': blockchain
            },
            'protection_chain': {
                'status': protection_status,
                'verification': protection_verification,
            },
            'legacy': {
                'verification': legacy_verification,
                'total_logs': len(p.audit.logs)
            }
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/blockchain-audit/mine', methods=['POST'])
def mine_pending_events():
    """
    Force mine pending events into a new block
    Only accessible by Level 5 users
    """
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        p = get_pipeline()

        if user_id:
            user = p.rbac.get_user(user_id)
            if not user or user.access_level < 5:
                return jsonify({
                    'success': False,
                    'error': 'Access Denied',
                    'message': 'Only Level 5 administrators can mine blocks.'
                }), 403

        # Force mine pending events
        new_block = p.audit.force_mine_block()

        if new_block:
            return jsonify({
                'success': True,
                'message': 'New block mined successfully',
                'block': new_block.to_dict()
            })
        else:
            return jsonify({
                'success': True,
                'message': 'No pending events to mine'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sample-documents', methods=['GET'])
def get_sample_documents():
    """Get sample documents from the dataset for testing"""
    try:
        import random
        # Try diverse dataset first, fallback to synthetic
        filepath = os.path.join(Config.DATA_DIR, "diverse_test_dataset.json")
        if not os.path.exists(filepath):
            filepath = os.path.join(Config.DATA_DIR, "synthetic_training_dataset.json")

        with open(filepath, 'r', encoding='utf-8') as f:
            all_docs = json.load(f)

        # Get random sample
        count = request.args.get('count', 5, type=int)
        count = min(count, len(all_docs))
        samples = random.sample(all_docs, count)

        return jsonify({
            'success': True,
            'count': len(samples),
            'documents': samples
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-dataset', methods=['POST'])
def generate_dataset():
    """Generate a new diverse test dataset with mixed Arabic/English documents"""
    try:
        data = request.get_json() or {}
        num_docs = data.get('count', 100)
        num_docs = min(max(num_docs, 10), 500)  # Limit between 10-500

        # Import and run the generator
        sys.path.insert(0, Config.DATA_DIR)
        from generate_diverse_dataset import generate_diverse_dataset as gen_dataset

        # Generate documents
        documents = gen_dataset(num_docs)

        # Save to file
        output_file = os.path.join(Config.DATA_DIR, "diverse_test_dataset.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

        # Count by classification
        counts = {}
        for doc in documents:
            level = doc["classification"]
            counts[level] = counts.get(level, 0) + 1

        return jsonify({
            'success': True,
            'message': f'Generated {len(documents)} diverse documents',
            'count': len(documents),
            'distribution': counts,
            'file': output_file,
            'features': [
                'Valid 14-digit Egyptian National IDs',
                'Egyptian passport numbers',
                'Mixed Arabic/English content',
                'Salary in EGP and USD formats',
                'Egyptian IBAN numbers',
                'Diverse document types'
            ]
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/dataset-info', methods=['GET'])
def get_dataset_info():
    """Get information about the current test dataset"""
    try:
        filepath = os.path.join(Config.DATA_DIR, "diverse_test_dataset.json")

        if not os.path.exists(filepath):
            return jsonify({
                'success': True,
                'exists': False,
                'message': 'No diverse dataset found. Generate one first.'
            })

        with open(filepath, 'r', encoding='utf-8') as f:
            documents = json.load(f)

        # Count by classification
        counts = {}
        formats = set()
        for doc in documents:
            level = doc["classification"]
            counts[level] = counts.get(level, 0) + 1
            if 'format' in doc:
                formats.add(doc['format'])

        # Get file modification time
        import datetime
        mtime = os.path.getmtime(filepath)
        modified = datetime.datetime.fromtimestamp(mtime).isoformat()

        return jsonify({
            'success': True,
            'exists': True,
            'count': len(documents),
            'distribution': counts,
            'formats': list(formats),
            'lastModified': modified
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/evaluate', methods=['POST'])
def run_evaluation():
    """
    Run evaluation on uploaded documents that have ground truth labels.
    Evaluates documents stored in secure_storage that have a true_label in metadata.
    """
    try:
        # Read all stored documents
        storage_dir = Config.STORAGE_DIR
        results = []

        if not os.path.exists(storage_dir):
            return jsonify({
                'success': False,
                'error': 'No documents found. Upload documents with ground truth labels first.'
            }), 404

        # Collect documents with ground truth labels
        for filename in os.listdir(storage_dir):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(storage_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                doc_data = json.load(f)

            # Only include documents that have a true_label
            metadata = doc_data.get('metadata', {})
            true_label = metadata.get('true_label')

            if true_label:
                pred_label = doc_data.get('classification')
                results.append({
                    'doc_id': doc_data.get('doc_id'),
                    'true_label': true_label,
                    'pred_label': pred_label,
                    'correct': true_label == pred_label,
                    'confidence': 0,  # Not stored, would need to re-read
                    'method': metadata.get('classification_method', 'unknown')
                })

        if not results:
            return jsonify({
                'success': False,
                'error': 'No documents with ground truth labels found. When uploading, provide the correct classification label.'
            }), 404

        # Calculate metrics per class
        classes = ['C0', 'C1', 'C2', 'C3']
        metrics = {}

        for cls in classes:
            # True positives: predicted cls and actually cls
            tp = sum(1 for r in results if r['pred_label'] == cls and r['true_label'] == cls)
            # False positives: predicted cls but actually something else
            fp = sum(1 for r in results if r['pred_label'] == cls and r['true_label'] != cls)
            # False negatives: actually cls but predicted something else
            fn = sum(1 for r in results if r['true_label'] == cls and r['pred_label'] != cls)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            metrics[cls] = {
                'precision': round(precision * 100, 1),
                'recall': round(recall * 100, 1),
                'f1': round(f1 * 100, 1),
                'support': sum(1 for r in results if r['true_label'] == cls),
                'tp': tp,
                'fp': fp,
                'fn': fn
            }

        # Overall accuracy
        correct = sum(1 for r in results if r['correct'])
        accuracy = round(correct / len(results) * 100, 1) if results else 0

        # Confusion matrix
        confusion = {}
        for true_cls in classes:
            confusion[true_cls] = {}
            for pred_cls in classes:
                confusion[true_cls][pred_cls] = sum(
                    1 for r in results
                    if r['true_label'] == true_cls and r['pred_label'] == pred_cls
                )

        return jsonify({
            'success': True,
            'total_docs': len(results),
            'accuracy': accuracy,
            'metrics': metrics,
            'confusion_matrix': confusion,
            'details': results
        })

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """Get a specific document by ID with access control"""
    try:
        storage_dir = Config.STORAGE_DIR
        filepath = os.path.join(storage_dir, f"{doc_id}.json")

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'error': 'Document not found',
                'error_code': 'DOC_NOT_FOUND',
                'message': f'The document "{doc_id}" does not exist in the system.'
            }), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)

        # Get user_id from query parameter
        user_id = request.args.get('user_id')
        p = get_pipeline()
        classification = doc_data.get('final_classification') or doc_data.get('classification', 'C1')
        doc_department = doc_data.get('department')

        # Check access control if user_id is provided
        if user_id:
            user = p.rbac.get_user(user_id)
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found',
                    'error_code': 'USER_NOT_FOUND',
                    'message': f'User "{user_id}" is not registered in the system. Please contact your administrator.'
                }), 403

            # Flagged documents are locked for regular users until DPO resolves the flag
            _flag = doc_data.get('flag')
            if _flag and _flag.get('status') == 'PENDING':
                if user.access_level < 5 and user.role != 'DPO':
                    return jsonify({
                        'success': False,
                        'error': 'Document Locked',
                        'error_code': 'FLAGGED_LOCKED',
                        'message': 'This document has been flagged for review and is locked until the DPO resolves the flag.'
                    }), 423

            access_result = p.rbac.check_access(user_id, classification, 'view', doc_department=doc_department)

            if not access_result.get('allowed'):
                denial_reason = access_result.get('reason', '')
                p.audit.log_event('ACCESS_DENIED', {
                    'document_id': doc_id,
                    'user_id': user_id,
                    'classification': classification,
                    'action': 'view',
                    'user_level': user.access_level,
                    'reason': denial_reason
                })
                if 'department' in denial_reason.lower():
                    deny_msg = f'Access denied: this {classification} document belongs to the {doc_department} department and your account is restricted to your own department.'
                    deny_code = 'DEPT_BLOCKED'
                else:
                    deny_msg = f'Access denied: your access level (L{user.access_level}) is insufficient to view {classification} documents.'
                    deny_code = 'LEVEL_BLOCKED'
                return jsonify({
                    'success': False,
                    'error': 'Access Denied',
                    'error_code': deny_code,
                    'message': deny_msg,
                    'details': {
                        'user': user.name,
                        'user_level': user.access_level,
                        'user_role': user.role,
                        'document_classification': classification,
                        'document_department': doc_department,
                        'reason': denial_reason
                    }
                }), 403

            p.audit.log_event('DOCUMENT_VIEWED', {
                'document_id': doc_id,
                'user_id': user_id,
                'user_name': user.name,
                'user_level': user.access_level,
                'classification': classification,
                'filename': doc_data.get('original_filename', doc_id),
            })

        # If document is encrypted, try to decrypt it
        content = None
        is_encrypted = doc_data.get('encrypted_data') is not None

        if is_encrypted and doc_data.get('encrypted_data'):
            try:
                # Decrypt the document
                encrypted_info = doc_data['encrypted_data']
                content = p.pqc.decrypt(
                    encrypted_info['ciphertext'],
                    encrypted_info['key_id'],
                    encrypted_info.get('encapsulated_key'),
                    encrypted_info.get('nonce'),
                    encrypted_info.get('shared_secret')
                )
            except Exception as e:
                content = f"[Encrypted - Decryption failed: {e}]"
        else:
            content = doc_data.get('original_text') or doc_data.get('text', '[No content available]')

        # Apply role-based redaction to the content before sending to the viewer
        redacted_fields = []
        heavy_redaction = False
        if user_id and content and not content.startswith('[Encrypted'):
            user_for_redact = p.rbac.get_user(user_id)
            # C3 + L3: heavy redaction — only name, job title, department, date visible
            if classification == 'C3' and user_for_redact and user_for_redact.access_level == 3:
                heavy_redaction = True
                visibility = {
                    'national_id': False, 'passport': False, 'iban': False,
                    'account_number': False, 'salary': False, 'phone': False,
                    'email': False, 'name': True, 'date_of_birth': True,
                    'address': False, 'risk_rating': False,
                    'source_of_funds': False, 'sanctions_result': False,
                }
            else:
                visibility = p.rbac.get_field_visibility(user_id)
            redaction_result = DocumentRedactor().redact(content, visibility)
            content = redaction_result['redacted_text']
            redacted_fields = redaction_result['redacted_fields']
            if redacted_fields:
                p.audit.log_event('DOCUMENT_REDACTED', {
                    'document_id': doc_id,
                    'user_id': user_id,
                    'redacted_fields': redacted_fields,
                    'redaction_count': redaction_result['redaction_count'],
                    'context': 'view',
                    'heavy_redaction': heavy_redaction,
                })

        # Auto integrity check on every document load
        integrity_check = None
        try:
            protection_chain = DocumentProtectionChain(
                storage_dir=Config.STORAGE_DIR,
            )
            integrity_check = protection_chain.verify_document(doc_id)
        except Exception:
            pass

        metadata = _enrich_document_metadata(doc_data)
        return jsonify({
            'success': True,
            'document': {
                'doc_id': doc_data.get('doc_id'),
                'classification': doc_data.get('final_classification') or doc_data.get('classification'),
                'timestamp': doc_data.get('timestamp'),
                'encrypted': is_encrypted,
                'content': content,
                'redacted_fields': redacted_fields,
                'heavy_redaction': heavy_redaction,
                'metadata': metadata,
                'department': doc_data.get('department'),
                'status': 'ACTIVE',
                'ai_classification': doc_data.get('ai_classification'),
                'ai_confidence': doc_data.get('ai_confidence'),
                'ai_reasoning': doc_data.get('ai_reasoning'),
                'final_classification': doc_data.get('final_classification') or doc_data.get('classification'),
                'original_filename': doc_data.get('original_filename'),
                'uploaded_by': doc_data.get('uploaded_by'),
                'integrity_check': integrity_check,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<doc_id>/preview-file', methods=['GET'])
def preview_document_file(doc_id):
    """Serve the original file for in-browser preview (view access required)"""
    try:
        storage_dir = Config.STORAGE_DIR
        filepath = os.path.join(storage_dir, f"{doc_id}.json")
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)

        user_id = request.args.get('user_id')
        classification = doc_data.get('classification', 'C1')
        p = get_pipeline()

        if user_id:
            user = p.rbac.get_user(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 403
            _flag_pf = doc_data.get('flag')
            if _flag_pf and _flag_pf.get('status') == 'PENDING':
                if user.access_level < 5 and user.role != 'DPO':
                    return jsonify({'success': False, 'error': 'Document locked pending DPO review', 'error_code': 'FLAGGED_LOCKED'}), 423
            doc_dept_pf = doc_data.get('department')
            access_result = p.rbac.check_access(user_id, classification, 'view', doc_department=doc_dept_pf)
            if not access_result.get('allowed'):
                return jsonify({'success': False, 'error': 'Access denied'}), 403
            p.audit.log_event('DOCUMENT_PREVIEWED', {
                'document_id': doc_id,
                'user_id': user_id,
                'user_name': user.name,
                'user_level': user.access_level,
                'classification': classification,
                'filename': doc_data.get('original_filename', doc_id),
            })

        file_bytes, filename = _get_original_file(doc_id)
        if file_bytes is None:
            return jsonify({'success': False, 'error': 'Original file not available'}), 404

        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        mime_map = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
        }
        mime = mime_map.get(ext, 'application/octet-stream')

        from flask import Response
        response = Response(file_bytes, mimetype=mime)
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<doc_id>/download', methods=['GET'])
def download_document(doc_id):
    """Download a document as a text file with access control"""
    try:
        storage_dir = Config.STORAGE_DIR
        filepath = os.path.join(storage_dir, f"{doc_id}.json")

        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'error': 'Document not found',
                'error_code': 'DOC_NOT_FOUND',
                'message': f'The document "{doc_id}" does not exist in the system.'
            }), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)

        # Get user_id from query parameter
        user_id = request.args.get('user_id')
        p = get_pipeline()
        classification = doc_data.get('final_classification') or doc_data.get('classification', 'C1')
        doc_department = doc_data.get('department')

        # Check access control if user_id is provided (download = same rules as view)
        if user_id:
            user = p.rbac.get_user(user_id)
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found',
                    'error_code': 'USER_NOT_FOUND',
                    'message': f'User "{user_id}" is not registered in the system. Please contact your administrator.'
                }), 403

            # Flagged documents are locked for regular users until DPO resolves the flag
            _flag_dl = doc_data.get('flag')
            if _flag_dl and _flag_dl.get('status') == 'PENDING':
                if user.access_level < 5 and user.role != 'DPO':
                    return jsonify({
                        'success': False,
                        'error': 'Document Locked',
                        'error_code': 'FLAGGED_LOCKED',
                        'message': 'This document has been flagged for review and is locked until the DPO resolves the flag.'
                    }), 423

            access_result = p.rbac.check_access(user_id, classification, 'view', doc_department=doc_department)

            if not access_result.get('allowed'):
                # Log the denied access
                p.audit.log_event('ACCESS_DENIED', {
                    'document_id': doc_id,
                    'user_id': user_id,
                    'classification': classification,
                    'action': 'download',
                    'user_level': user.access_level,
                    'reason': access_result.get('reason')
                })

                return jsonify({
                    'success': False,
                    'error': 'Access Denied',
                    'error_code': 'ACCESS_DENIED',
                    'message': f'You do not have permission to download this document.',
                    'details': {
                        'user': user.name,
                        'user_level': user.access_level,
                        'user_role': user.role,
                        'document_classification': classification,
                        'required_level': get_required_level(classification, 'download'),
                        'reason': access_result.get('reason')
                    }
                }), 403

            # Log successful download
            p.audit.log_event('DOCUMENT_DOWNLOADED', {
                'document_id': doc_id,
                'user_id': user_id,
                'user_name': user.name,
                'user_level': user.access_level,
                'classification': classification,
                'download_type': 'ocr_text',
                'filename': doc_data.get('original_filename', doc_id),
            })

        # If document is encrypted, try to decrypt it
        content = None
        is_encrypted = doc_data.get('encrypted_data') is not None

        if is_encrypted and doc_data.get('encrypted_data'):
            try:
                encrypted_info = doc_data['encrypted_data']
                content = p.pqc.decrypt(
                    encrypted_info['ciphertext'],
                    encrypted_info['key_id'],
                    encrypted_info.get('encapsulated_key'),
                    encrypted_info.get('nonce'),
                    encrypted_info.get('shared_secret')
                )
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': 'Decryption failed',
                    'error_code': 'DECRYPT_FAILED',
                    'message': f'Could not decrypt the document: {e}'
                }), 500
        else:
            content = doc_data.get('original_text') or doc_data.get('text', '')

        if not content:
            return jsonify({
                'success': False,
                'error': 'No content',
                'error_code': 'NO_CONTENT',
                'message': 'This document has no content available.'
            }), 404

        # Apply role-based redaction if a user is identified (same as view endpoint)
        if user_id:
            user_for_redact = p.rbac.get_user(user_id)
            # C3 + L3: heavy redaction — only name and date_of_birth visible
            if classification == 'C3' and user_for_redact and user_for_redact.access_level == 3:
                visibility = {
                    'national_id': False, 'passport': False, 'iban': False,
                    'account_number': False, 'salary': False, 'phone': False,
                    'email': False, 'name': True, 'date_of_birth': True,
                    'address': False, 'risk_rating': False,
                    'source_of_funds': False, 'sanctions_result': False,
                }
            else:
                visibility = p.rbac.get_field_visibility(user_id)
            redaction_result = DocumentRedactor().redact(content, visibility)
            content = redaction_result['redacted_text']
            if redaction_result['redacted_fields']:
                p.audit.log_event('DOCUMENT_REDACTED', {
                    'document_id': doc_id,
                    'user_id': user_id,
                    'redacted_fields': redaction_result['redacted_fields'],
                    'redaction_count': redaction_result['redaction_count'],
                    'context': 'download',
                })

        response = Response(
            content,
            mimetype='text/plain; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={doc_id}_ocr.txt',
                'Content-Type': 'text/plain; charset=utf-8',
            }
        )
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# HUMAN-IN-THE-LOOP VERIFICATION ENDPOINTS (Change 2)
# ============================================================================

def _get_doc_data(doc_id: str):
    """Load document JSON from storage. Returns dict or None."""
    filepath = os.path.join(Config.STORAGE_DIR, f"{doc_id}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_doc_data(doc_id: str, doc_data: dict):
    filepath = os.path.join(Config.STORAGE_DIR, f"{doc_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(doc_data, f, indent=2, ensure_ascii=False)


# ============================================================================
# WATERMARKING (Change 5 — department name added)
# ============================================================================

def _load_pil_font(size):
    """Try to load a TrueType font, fall back to PIL default."""
    from PIL import ImageFont
    for path in [
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/Arial.ttf',
        '/System/Library/Fonts/SFNSText.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _build_redacted_ocr_pdf(doc_id, doc_data, classification, date_str, department_label,
                            field_visibility, pipeline, user_id):
    """
    Build a watermarked PDF from the stored OCR text with text-based redaction applied.
    Used as a fallback when the original file is an image (no text layer for visual redaction).
    Returns a Flask Response.
    """
    import fitz as _fitz
    is_encrypted = doc_data.get('encrypted_data') is not None
    if is_encrypted and doc_data.get('encrypted_data'):
        try:
            enc = doc_data['encrypted_data']
            content = pipeline.pqc.decrypt(
                enc['ciphertext'], enc['key_id'],
                enc.get('encapsulated_key'), enc.get('nonce'), enc.get('shared_secret'),
            )
        except Exception:
            content = '[Encrypted — content unavailable]'
    else:
        content = doc_data.get('original_text') or doc_data.get('text', '')
    if not content:
        content = '[No content available]'

    redaction_result = DocumentRedactor().redact(content, field_visibility)
    content = redaction_result['redacted_text']
    if redaction_result['redacted_fields'] and user_id:
        pipeline.audit.log_event('DOCUMENT_REDACTED', {
            'document_id': doc_id,
            'user_id': user_id,
            'redacted_fields': redaction_result['redacted_fields'],
            'redaction_count': redaction_result['redaction_count'],
            'context': 'download-ocr-fallback',
        })

    import io as _io
    margin, page_w, page_h, font_size = 50, 595, 842, 10
    line_height = font_size * 1.5
    max_chars = int((page_w - margin * 2) / (font_size * 0.55))
    lines_per_page = int((page_h - margin * 2) / line_height)
    words = content.split()
    wrapped, current = [], ''
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + ' ' + word).lstrip()
        else:
            wrapped.append(current)
            current = word
    if current:
        wrapped.append(current)
    page_chunks = [wrapped[i:i + lines_per_page] for i in range(0, max(len(wrapped), 1), lines_per_page)]
    if not page_chunks:
        page_chunks = [['']]

    pdf = _fitz.open()
    for chunk in page_chunks:
        page = pdf.new_page(width=page_w, height=page_h)
        page.insert_text(
            _fitz.Point(margin, margin - 14),
            f"{doc_id}  ·  {classification}  ·  {date_str}",
            fontsize=8, color=(0.5, 0.5, 0.5),
        )
        for i, line in enumerate(chunk):
            page.insert_text(_fitz.Point(margin, margin + i * line_height), line,
                             fontsize=font_size, color=(0.1, 0.1, 0.1))
        _apply_pdf_watermark(page, classification, date_str, department_label)
    output = _io.BytesIO()
    pdf.save(output)
    pdf.close()
    return Response(
        output.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{doc_id}_watermarked.pdf"',
            'Access-Control-Expose-Headers': 'Content-Disposition',
        },
    )


def _apply_pdf_visual_redaction(fitz_doc, field_visibility: dict) -> None:
    """
    Apply visual (black-box) redaction to a fitz PDF document in-place.

    For every pattern in the redaction engine whose field is hidden in
    field_visibility, find literal matches in the PDF text layer and
    cover them with a black redaction annotation.
    """
    import fitz as _fitz
    from src.redaction import _PATTERNS

    for page in fitz_doc:
        page_text = page.get_text()
        added = False
        for field_type, pattern in _PATTERNS:
            if field_visibility.get(field_type, True):
                continue  # field is visible — don't redact
            for match in pattern.finditer(page_text):
                matched_str = match.group(0).strip()
                if not matched_str:
                    continue
                rects = page.search_for(matched_str, quads=False)
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    added = True
        if added:
            page.apply_redactions()


def _apply_pdf_watermark(fitz_page, classification, date_str, department: str = None):
    """Tile a diagonal watermark across a single PyMuPDF page."""
    if classification == 'C0':
        return  # Public documents do not receive a watermark
    import fitz
    colour_map = {
        'C0': (0.18, 0.62, 0.18),
        'C1': (0.13, 0.35, 0.82),
        'C2': (0.80, 0.38, 0.02),
        'C3': (0.78, 0.08, 0.08),
    }
    colour = colour_map.get(classification, (0.45, 0.45, 0.45))
    dept_part = department if department and department not in ('All', 'None') else ''
    dept_seg = f" — {dept_part}" if dept_part else ''
    line1 = f"{classification}{dept_seg}"
    line2 = date_str

    pw, ph = fitz_page.rect.width, fitz_page.rect.height
    col_step = 420
    row_step = 190

    for row in range(-1, int(ph / row_step) + 3):
        for col in range(-1, int(pw / col_step) + 3):
            x = col * col_step + (row % 2) * (col_step / 2)
            y = row * row_step
            if x < -450 or x > pw + 450:
                continue
            if y < -200 or y > ph + 380:
                continue

            p1 = fitz.Point(x, y)
            fitz_page.insert_text(
                p1, line1,
                fontsize=15, color=colour,
                fill_opacity=0.30,
                morph=(p1, fitz.Matrix(45)),
            )
            p2 = fitz.Point(x + 6, y + 20)
            fitz_page.insert_text(
                p2, line2,
                fontsize=11, color=colour,
                fill_opacity=0.22,
                morph=(p2, fitz.Matrix(45)),
            )


def _apply_image_watermark(pil_img, classification, date_str, department: str = None):
    """Tile a diagonal watermark across a PIL Image (RGBA)."""
    if classification == 'C0':
        return pil_img  # Public documents do not receive a watermark
    from PIL import Image, ImageDraw
    colour_map = {
        'C0': (20, 140, 20),
        'C1': (25, 75, 200),
        'C2': (195, 85, 5),
        'C3': (195, 15, 15),
    }
    r, g, b = colour_map.get(classification, (90, 90, 90))

    iw, ih = pil_img.size
    font_size_l = max(22, iw // 28)
    font_size_s = max(15, iw // 42)
    font_l = _load_pil_font(font_size_l)
    font_s = _load_pil_font(font_size_s)

    dept_part = department if department and department not in ('All', 'None') else ''
    dept_seg = f" — {dept_part}" if dept_part else ''
    line1 = f"{classification}{dept_seg}"
    line2 = date_str

    # Measure sizes
    dummy = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    b1 = dummy.textbbox((0, 0), line1, font=font_l)
    b2 = dummy.textbbox((0, 0), line2, font=font_s)
    tw1, th1 = b1[2] - b1[0], b1[3] - b1[1]
    th2 = b2[3] - b2[1]
    pad = 8
    tile_w = tw1 + pad * 2
    tile_h = th1 + th2 + pad * 3

    # Build a single rotated tile
    tile = Image.new('RGBA', (tile_w, tile_h + 10), (255, 255, 255, 0))
    td = ImageDraw.Draw(tile)
    td.text((pad, pad), line1, font=font_l, fill=(r, g, b, 75))
    td.text((pad, pad + th1 + pad), line2, font=font_s, fill=(r, g, b, 60))
    rotated = tile.rotate(45, expand=True)
    rw, rh = rotated.size

    overlay = Image.new('RGBA', pil_img.size, (255, 255, 255, 0))
    step_x = rw + 80
    step_y = rh + 80
    for oy in range(-rh, ih + rh, step_y):
        for ox in range(-rw, iw + rw, step_x):
            overlay.paste(rotated, (ox, oy), rotated)

    return Image.alpha_composite(pil_img, overlay)


@app.route('/api/documents/<doc_id>/download-watermarked', methods=['POST'])
def download_watermarked(doc_id):
    """Download the original file (PDF or image) with a classification watermark overlaid."""
    import io
    try:
        storage_dir = Config.STORAGE_DIR
        filepath = os.path.join(storage_dir, f"{doc_id}.json")

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)

        classification = doc_data.get('final_classification') or doc_data.get('classification', 'C1')
        doc_department = doc_data.get('department')
        date_str = datetime.now().strftime('%Y-%m-%d')
        department_wm = doc_department
        process_wm = doc_data.get('process', '')
        if process_wm and process_wm != 'Unknown':
            department_wm = f"{department_wm} — {process_wm}" if department_wm else process_wm

        # Access check (download = same as view)
        user_id = request.args.get('user_id') or request.form.get('user_id')
        p = get_pipeline()
        needs_heavy_redaction = False
        if user_id:
            user = p.rbac.get_user(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found', 'error_code': 'USER_NOT_FOUND'}), 403
            _flag_wm = doc_data.get('flag')
            if _flag_wm and _flag_wm.get('status') == 'PENDING':
                if user.access_level < 5 and user.role != 'DPO':
                    return jsonify({'success': False, 'error': 'Document locked pending DPO review', 'error_code': 'FLAGGED_LOCKED'}), 423
            access_result = p.rbac.check_access(user_id, classification, 'view', doc_department=doc_department)
            if not access_result.get('allowed'):
                return jsonify({
                    'success': False, 'error': 'Access Denied', 'error_code': 'ACCESS_DENIED',
                    'message': 'You do not have permission to download this document.',
                    'reason': access_result.get('reason')
                }), 403
            # C3 + L3 must receive a redacted OCR PDF, not the raw original file
            if classification == 'C3' and user.access_level == 3:
                needs_heavy_redaction = True
            p.audit.log_event('DOCUMENT_DOWNLOADED', {
                'document_id': doc_id,
                'user_id': user_id,
                'user_name': user.name,
                'user_level': user.access_level,
                'classification': classification,
                'download_type': 'watermarked',
                'filename': doc_data.get('original_filename', doc_id),
            })

        uploaded_file = request.files.get('file')
        if not uploaded_file:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        filename = uploaded_file.filename or ''
        file_bytes = uploaded_file.read()

        heavy_visibility = {
            'national_id': False, 'passport': False, 'iban': False,
            'account_number': False, 'salary': False, 'phone': False,
            'email': False, 'name': True, 'date_of_birth': True,
            'address': False, 'risk_rating': False,
            'source_of_funds': False, 'sanctions_result': False,
        }

        if filename.lower().endswith('.pdf'):
            import fitz
            doc = fitz.open(stream=file_bytes, filetype='pdf')
            if needs_heavy_redaction:
                _apply_pdf_visual_redaction(doc, heavy_visibility)
            for page in doc:
                _apply_pdf_watermark(page, classification, date_str, department_wm)
            output = io.BytesIO()
            doc.save(output)
            doc.close()
            return Response(
                output.getvalue(),
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="{doc_id}_watermarked.pdf"',
                    'Access-Control-Expose-Headers': 'Content-Disposition',
                },
            )
        elif needs_heavy_redaction:
            # Images have no text layer — fall back to redacted OCR text PDF
            return _build_redacted_ocr_pdf(doc_id, doc_data, classification, date_str,
                                           department_wm, heavy_visibility, p, user_id)
        else:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes)).convert('RGBA')
            result = _apply_image_watermark(img, classification, date_str, department_wm)

            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
            fmt = 'JPEG' if ext in ('jpg', 'jpeg') else 'PNG'
            mime = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
            if fmt == 'JPEG':
                result = result.convert('RGB')

            output = io.BytesIO()
            result.save(output, format=fmt, quality=92)
            return Response(
                output.getvalue(),
                mimetype=mime,
                headers={
                    'Content-Disposition': f'attachment; filename="{doc_id}_watermarked.{ext}"',
                    'Access-Control-Expose-Headers': 'Content-Disposition',
                },
            )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<doc_id>/download-text-watermarked', methods=['GET'])
def download_text_watermarked(doc_id):
    """
    Download the original file with a classification watermark.
    Used by the History view.
    - If the original file was saved at upload time, watermark and return it.
    - Otherwise fall back to generating a watermarked PDF from the stored OCR text.
    """
    import io
    try:
        storage_dir = Config.STORAGE_DIR
        filepath = os.path.join(storage_dir, f"{doc_id}.json")

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)

        classification = doc_data.get('final_classification') or doc_data.get('classification', 'C1')
        doc_department = doc_data.get('department')
        date_str = datetime.now().strftime('%Y-%m-%d')
        department_wm2 = doc_department
        process_wm = doc_data.get('process', '')
        if process_wm and process_wm != 'Unknown':
            department_wm2 = f"{department_wm2} — {process_wm}" if department_wm2 else process_wm

        # Access check (download = same as view)
        user_id = request.args.get('user_id')
        p = get_pipeline()
        needs_heavy_redaction = False
        if user_id:
            user = p.rbac.get_user(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found', 'error_code': 'USER_NOT_FOUND'}), 403
            _flag_wm2 = doc_data.get('flag')
            if _flag_wm2 and _flag_wm2.get('status') == 'PENDING':
                if user.access_level < 5 and user.role != 'DPO':
                    return jsonify({'success': False, 'error': 'Document locked pending DPO review', 'error_code': 'FLAGGED_LOCKED'}), 423
            access_result = p.rbac.check_access(user_id, classification, 'view', doc_department=doc_department)
            if not access_result.get('allowed'):
                return jsonify({
                    'success': False, 'error': 'Access Denied', 'error_code': 'ACCESS_DENIED',
                    'message': 'You do not have permission to download this document.',
                    'reason': access_result.get('reason')
                }), 403
            # C3 + L3 must receive a redacted OCR PDF, not the raw original file
            if classification == 'C3' and user.access_level == 3:
                needs_heavy_redaction = True

        heavy_visibility = {
            'national_id': False, 'passport': False, 'iban': False,
            'account_number': False, 'salary': False, 'phone': False,
            'email': False, 'name': True, 'date_of_birth': True,
            'address': False, 'risk_rating': False,
            'source_of_funds': False, 'sanctions_result': False,
        }

        # ── Try to use the stored original file ──────────────────────────────
        file_bytes, orig_filename = _get_original_file(doc_id)

        if file_bytes is not None and orig_filename:
            filename = orig_filename
            if filename.lower().endswith('.pdf'):
                import fitz
                doc = fitz.open(stream=file_bytes, filetype='pdf')
                # Apply visual redaction to the PDF pages for restricted users
                if needs_heavy_redaction:
                    _apply_pdf_visual_redaction(doc, heavy_visibility)
                for page in doc:
                    _apply_pdf_watermark(page, classification, date_str, department_wm2)
                output = io.BytesIO()
                doc.save(output)
                doc.close()
                return Response(
                    output.getvalue(),
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': f'attachment; filename="{doc_id}_watermarked.pdf"',
                        'Access-Control-Expose-Headers': 'Content-Disposition',
                    },
                )
            elif not needs_heavy_redaction:
                # Image with no redaction needed — serve directly with watermark
                from PIL import Image
                img = Image.open(io.BytesIO(file_bytes)).convert('RGBA')
                result = _apply_image_watermark(img, classification, date_str, department_wm2)
                ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
                fmt = 'JPEG' if ext in ('jpg', 'jpeg') else 'PNG'
                mime = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
                if fmt == 'JPEG':
                    result = result.convert('RGB')
                output = io.BytesIO()
                result.save(output, format=fmt, quality=92)
                return Response(
                    output.getvalue(),
                    mimetype=mime,
                    headers={
                        'Content-Disposition': f'attachment; filename="{doc_id}_watermarked.{ext}"',
                        'Access-Control-Expose-Headers': 'Content-Disposition',
                    },
                )
            # else: image + needs_heavy_redaction → fall through to OCR text fallback

        # ── Fallback: build a watermarked PDF from stored OCR text ───────────
        # Also used for images when heavy redaction is required (images have no text layer).
        redact_visibility = heavy_visibility if needs_heavy_redaction else (
            p.rbac.get_field_visibility(user_id) if user_id else {f: True for f in heavy_visibility}
        )
        return _build_redacted_ocr_pdf(
            doc_id, doc_data, classification, date_str, department_wm2,
            redact_visibility, p, user_id,
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# BLOCKCHAIN PROTECTION & BENCHMARK ENDPOINTS
# ============================================================================

@app.route('/api/documents/<doc_id>/verify', methods=['GET'])
def verify_document_integrity(doc_id):
    """
    Verify a single document's blockchain integrity.
    Re-hashes content and compares against stored blockchain hash.
    """
    try:
        protection_chain = DocumentProtectionChain(
            storage_dir=Config.STORAGE_DIR,
        )
        result = protection_chain.verify_document(doc_id)
        return jsonify({
            'success': True,
            **result,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents/protect-all', methods=['POST'])
def protect_all_documents():
    """
    Retroactively protect all stored documents that are not yet in the protection chain.
    Safe to call multiple times — already-protected documents are skipped.
    """
    try:
        user_id = request.json.get('user_id') if request.is_json else None
        protection_chain = DocumentProtectionChain(storage_dir=Config.STORAGE_DIR)
        results = protection_chain.protect_all_from_storage(user_id=user_id)
        return jsonify({
            'success': True,
            'protected_count': len(results['protected']),
            'skipped_count': len(results['skipped']),
            'failed_count': len(results['failed']),
            **results,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/benchmark/ab-test', methods=['POST'])
def run_ab_test():
    """
    Run A/B comparison: Mode A (no blockchain protection) vs Mode B (with protection).
    Request body (optional):
    {
        "count": 10,           // number of documents (default 10, max 50)
        "documents": [...]     // optional: provide your own documents
    }
    """
    try:
        data = request.get_json() or {}
        count = min(data.get('count', 10), 50)
        documents = data.get('documents') or load_benchmark_documents(count)

        p = get_pipeline()
        settings = get_settings()

        runner = ABTestRunner(p, settings)
        result = runner.run(documents)

        return jsonify({
            'success': True,
            'summary': {
                'total_documents': result['total_documents'],
                'classification_changes': result['classification_changes'],
                'avg_time_without_ms': result['avg_time_without_ms'],
                'avg_time_with_ms': result['avg_time_with_ms'],
                'overhead_pct': result['overhead_pct'],
            },
            'csv_path': result.get('csv_path'),
            'json_path': result.get('json_path'),
            'results': result['results'],
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/benchmark/full', methods=['POST'])
def run_full_benchmark():
    """
    Run full benchmark suite: sequential + concurrent testing.
    Request body (optional):
    {
        "count": 50,                        // docs to use (default 20, max 50)
        "concurrent_levels": [5,10,15,20,25] // concurrent user counts to test
    }
    """
    try:
        data = request.get_json() or {}
        count = min(data.get('count', 20), 50)
        concurrent_levels = data.get('concurrent_levels', [5, 10, 15, 20, 25])
        documents = data.get('documents') or load_benchmark_documents(count)

        p = get_pipeline()
        settings = get_settings()

        benchmark = PerformanceBenchmark(p, settings)
        result = benchmark.run(documents, concurrent_levels=concurrent_levels)

        return jsonify({
            'success': True,
            'report': {
                'timestamp': result['timestamp'],
                'total_documents': result['total_documents'],
                'sequential': result['sequential'],
                'concurrent': result['concurrent'],
                'recommendation': result['recommendation'],
            },
            'json_path': result.get('json_path'),
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/benchmark/results', methods=['GET'])
def list_benchmark_results():
    """List all previous benchmark result files."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(base_dir, 'results', 'benchmarks')

        if not os.path.exists(results_dir):
            return jsonify({'success': True, 'results': []})

        files = []
        for filename in sorted(os.listdir(results_dir), reverse=True):
            filepath = os.path.join(results_dir, filename)
            stat = os.stat(filepath)
            entry = {
                'filename': filename,
                'size_bytes': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
            # For JSON files, try to read the recommendation
            if filename.endswith('.json'):
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    entry['recommendation'] = data.get('recommendation', {}).get('decision')
                    entry['type'] = 'ab_test' if 'results' in data else 'full_benchmark'
                except Exception:
                    pass
            files.append(entry)

        return jsonify({'success': True, 'results': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DIGITAL SIGNATURE ENDPOINTS
# ============================================================================

@app.route('/api/documents/<doc_id>/verify-signature', methods=['GET'])
def verify_document_signature(doc_id):
    """
    Verify a single document's RSA-PSS digital signature.
    Re-hashes content and verifies the cryptographic signature.
    """
    try:
        sig_manager = DocumentSignatureManager()
        result = sig_manager.verify_signature(doc_id)
        return jsonify({
            'success': True,
            **result,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/benchmark/signature-comparison', methods=['POST'])
def run_signature_comparison():
    """
    Run three-way benchmark: baseline vs blockchain vs digital signature.
    Request body (optional):
    {
        "count": 10,           // number of documents (default 10, max 50)
        "documents": [...]     // optional: provide your own documents
    }
    """
    try:
        data = request.get_json() or {}
        count = min(data.get('count', 10), 50)
        documents = data.get('documents') or load_benchmark_documents(count)

        p = get_pipeline()
        settings = get_settings()

        runner = ThreeWayBenchmarkRunner(p, settings)
        result = runner.run(documents)

        return jsonify({
            'success': True,
            'summary': {
                'total_documents': result['total_documents'],
                'classification_changes': result['classification_changes'],
                'mode_stats': result['mode_stats'],
            },
            'analysis': result.get('analysis', {}),
            'csv_path': result.get('csv_path'),
            'json_path': result.get('json_path'),
            'results': result['results'],
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/signature-status', methods=['GET'])
def get_signature_status():
    """Get digital signature system status."""
    try:
        sig_manager = DocumentSignatureManager()
        status = sig_manager.get_status()
        return jsonify({
            'success': True,
            'signature_status': status,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DATA CATALOGUE ENDPOINT
# ============================================================================

@app.route('/api/data-catalogue', methods=['GET'])
def get_data_catalogue():
    """
    Return the Critical Data Elements (CDE) catalogue with field definitions,
    sensitivity levels, and legal references (Egypt PDPL, CBE Framework, FATF).
    """
    catalogue = [
        {
            "field": "national_id",
            "label": "National ID Number",
            "type": "PII — Identity",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "Egypt PDPL Law No. 151/2020 — Art. 2 (sensitive personal data)",
                "CBE Financial Cybersecurity Framework 2020 — Sec. 3.2 (need-to-know)",
                "ISO 27001:2022 Annex A 5.34"
            ],
            "description": "14-digit Egyptian national ID number issued by CAPMAS."
        },
        {
            "field": "passport",
            "label": "Passport Number",
            "type": "PII — Identity",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "Egypt PDPL Law No. 151/2020 — Art. 2",
                "FATF Recommendation 10 — CDD requirements"
            ],
            "description": "International travel document identifier."
        },
        {
            "field": "iban",
            "label": "IBAN",
            "type": "Financial — Account",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "CBE Financial Cybersecurity Framework 2020 — Sec. 4.1",
                "ISO 27001:2022 Annex A 8.10",
                "NIST SP 800-53 AC-6"
            ],
            "description": "29-character Egyptian IBAN (EG + 2 check digits + 25 BBAN)."
        },
        {
            "field": "account_number",
            "label": "Bank Account Number",
            "type": "Financial — Account",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "CBE Financial Cybersecurity Framework 2020 — Sec. 4.1",
                "NIST SP 800-53 AC-6"
            ],
            "description": "Internal bank account reference number."
        },
        {
            "field": "salary",
            "label": "Salary / Income",
            "type": "Financial — Income",
            "sensitivity": "MEDIUM",
            "min_level_to_view": 3,
            "legal_references": [
                "Egypt PDPL Law No. 151/2020 — Art. 2 (financial data)",
                "ISO 27001:2022 Annex A 5.15"
            ],
            "description": "Employee or applicant monthly/annual income in EGP."
        },
        {
            "field": "risk_rating",
            "label": "Customer Risk Rating",
            "type": "AML / Compliance",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "FATF Recommendation 10 — risk-based CDD",
                "CBE AML/CFT Guidelines 2019",
                "Egypt AML Law No. 80/2002 (amended 2014)"
            ],
            "description": "Composite risk score (Low / Medium / High / Very High) assigned during KYC."
        },
        {
            "field": "sanctions_check",
            "label": "Sanctions Screening Result",
            "type": "AML / Compliance",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "FATF Recommendation 6 — targeted financial sanctions",
                "UN Security Council Resolutions",
                "CBE AML/CFT Guidelines 2019"
            ],
            "description": "Result of OFAC, UN, and local sanctions list screening."
        },
        {
            "field": "source_of_funds",
            "label": "Source of Funds / Wealth",
            "type": "AML / Compliance",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "FATF Recommendation 10 — enhanced CDD",
                "Egypt AML Law No. 80/2002 (amended 2014)"
            ],
            "description": "Declared origin of the customer's wealth or transaction funds."
        },
        {
            "field": "pep_flag",
            "label": "PEP Status",
            "type": "AML / Compliance",
            "sensitivity": "HIGH",
            "min_level_to_view": 4,
            "legal_references": [
                "FATF Recommendation 12 — Politically Exposed Persons",
                "CBE AML/CFT Guidelines 2019 — Sec. 5"
            ],
            "description": "Indicates whether the customer is a Politically Exposed Person or close associate."
        },
        {
            "field": "kyc_indicator",
            "label": "KYC Completion Status",
            "type": "Compliance — Onboarding",
            "sensitivity": "MEDIUM",
            "min_level_to_view": 4,
            "legal_references": [
                "FATF Recommendation 10",
                "CBE Regulation on Customer Due Diligence 2020"
            ],
            "description": "Flag indicating whether KYC documentation is complete, pending, or expired."
        },
        {
            "field": "date_of_birth",
            "label": "Date of Birth",
            "type": "PII — Demographic",
            "sensitivity": "MEDIUM",
            "min_level_to_view": 3,
            "legal_references": [
                "Egypt PDPL Law No. 151/2020 — Art. 2",
                "ISO 27001:2022 Annex A 5.34"
            ],
            "description": "Customer date of birth used for identity verification and eligibility checks."
        },
        {
            "field": "rim_number",
            "label": "RIM Number",
            "type": "Banking — Reference",
            "sensitivity": "MEDIUM",
            "min_level_to_view": 3,
            "legal_references": [
                "CBE Financial Cybersecurity Framework 2020 — Sec. 3.2"
            ],
            "description": "Relationship / Retail Identity Management number — unique customer reference in core banking."
        },
        {
            "field": "mobile",
            "label": "Mobile Phone Number",
            "type": "PII — Contact",
            "sensitivity": "LOW",
            "min_level_to_view": 2,
            "legal_references": [
                "Egypt PDPL Law No. 151/2020 — Art. 2"
            ],
            "description": "Customer mobile number used for OTP and notifications."
        },
    ]
    return jsonify({'success': True, 'catalogue': catalogue, 'total': len(catalogue)})


# ============================================================================
# MAIN
# ============================================================================

def _startup_protect_all():
    """On startup, retroactively protect any stored documents not yet in the chain."""
    try:
        protection_chain = DocumentProtectionChain(storage_dir=Config.STORAGE_DIR)
        results = protection_chain.protect_all_from_storage(user_id='system_startup')
        if results['protected']:
            print(f"🔗 Startup: retroactively protected {len(results['protected'])} document(s).")
    except Exception as e:
        print(f"⚠️  Startup protection failed: {e}")


_startup_protect_all()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🌐 DOCUMENT CLASSIFICATION WEB API")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /                     - Main UI")
    print("  GET  /api/health           - Health check")
    print("  POST /api/classify         - Classify single document")
    print("  POST /api/classify/batch   - Classify multiple documents")
    print("  GET  /api/statistics       - Get pipeline statistics")
    print("  GET  /api/users            - Get available users")
    print("  GET  /api/documents        - Get stored documents")
    print("  GET  /api/audit-logs       - Get audit trail")
    print("  GET  /api/sample-documents - Get random sample documents")
    print("\n" + "=" * 60)
    print("🚀 Starting server at http://localhost:5001")
    print("=" * 60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
