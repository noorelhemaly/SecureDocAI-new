/**
 * API Service - Connects React UI to Flask Backend
 */

const API_BASE = 'http://127.0.0.1:5001';

export interface ClassificationResult {
  success: boolean;
  doc_id: string;
  classification: 'C0' | 'C1' | 'C2' | 'C3';
  ocr_job_seconds?: number;  // Server-measured total OCR + classification time (images only)
  confidence: number;
  confidence_factors?: {
    agreement: number;
    evidence: number;
  };
  confidence_explanation?: string;
  llm_raw_confidence?: number;
  method: string;
  llm_classification: string;
  rules_classification: string;
  agreement: boolean;
  reasoning: string;
  triggers: string[];
  encrypted: boolean;
  storage_path: string;
  timestamp: string;
  access?: {
    user_id: string;
    granted: boolean;
    reason?: string;
  };
}

export interface User {
  user_id: string;
  name: string;
  role: string;
  access_level: number;
  department: string;
}

export interface Statistics {
  documents_processed: number;
  documents_stored: number;
  classifications: {
    C0: number;
    C1: number;
    C2: number;
    C3: number;
  };
  encrypted_documents: number;
  audit: {
    total_events: number;
    chain_valid: boolean;
  };
  event_types: Record<string, number>;
}

export interface StoredDocument {
  doc_id: string;
  classification: 'C0' | 'C1' | 'C2' | 'C3';
  timestamp: string;
  encrypted: boolean;
  text_length: number;
  method?: string;
  reasoning?: string;
  confidence?: number;
  llm_classification?: string;
  rules_classification?: string | null;
  triggers?: string[];
}

export interface AuditLog {
  event_id: string;
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface SampleDocument {
  id: string;
  text: string;
  label?: string;
}

export interface ClassificationSettings {
  confidenceThreshold: number;
  hybridMode: 'conservative' | 'balanced' | 'aggressive';
  autoEscalate: boolean;
  autoEncryptC2C3: boolean;
  enableBlockchainProtection: boolean;
  enableDigitalSignature: boolean;
}

// Health check
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    const data = await response.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}

// Classify a single document
export async function classifyDocument(
  text: string,
  docId?: string,
  userId?: string,
  settings?: Partial<ClassificationSettings>,
  trueLabel?: string  // Ground truth label for evaluation
): Promise<ClassificationResult> {
  const response = await fetch(`${API_BASE}/api/classify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      doc_id: docId || `DOC_${Date.now()}`,
      text,
      user_id: userId,
      settings: settings,
      true_label: trueLabel || undefined,
    }),
  });

  if (!response.ok) {
    throw new Error('Classification failed');
  }

  return response.json();
}

// Classify a PDF document (with server-side text extraction).
// Image files are processed asynchronously via Qwen2.5-VL OCR —
// this function polls automatically and resolves when the job is done.
export async function classifyPDF(
  file: File,
  docId?: string,
  userId?: string,
): Promise<ClassificationResult> {
  const formData = new FormData();
  formData.append('file', file);
  if (docId) formData.append('doc_id', docId);
  if (userId) formData.append('user_id', userId);

  const response = await fetch(`${API_BASE}/api/classify/pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'PDF classification failed');
  }

  const data = await response.json();

  // Image OCR is offloaded to a background job — poll until complete
  if (data.status === 'processing' && data.job_id) {
    return _pollOcrJob(data.job_id);
  }

  return data as ClassificationResult;
}

async function _pollOcrJob(jobId: string): Promise<ClassificationResult> {
  const POLL_INTERVAL_MS = 2000;
  const MAX_WAIT_MS = 5 * 60 * 1000; // 5 minutes
  const deadline = Date.now() + MAX_WAIT_MS;

  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));

    const resp = await fetch(`${API_BASE}/api/ocr-job/${encodeURIComponent(jobId)}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error((err as { error?: string }).error || 'OCR job failed');
    }
    const job = await resp.json();
    if (job.status === 'processing') continue;
    if (job.status === 'error') throw new Error(job.error || 'OCR job failed');
    return job as ClassificationResult;
  }

  throw new Error('OCR timed out after 5 minutes');
}

// --- Pipeline steps (for step-by-step backend visualization) ---

export interface PipelineExtraction {
  method: 'text' | 'ocr' | 'none';
  pages: number;
  text_length: number;
  success?: boolean;
  error?: string | null;
  source?: 'pdf' | 'image';
  ocr_used?: boolean;
  direct_text_length?: number;
  ocr_text_length?: number;
  language?: string | null;
  dpi?: number | null;
  tesseract_available?: boolean;
  tesseract_version?: string | null;
  notes?: string | null;
  pdf2image_available?: boolean;
  pymupdf_available?: boolean;
  image_mode?: string | null;
  image_size?: number[] | null;
  filename?: string | null;
}

export interface PipelineStepsResult {
  success: boolean;
  doc_id: string;
  filename?: string;
  extraction: PipelineExtraction | null;
  pipeline_result: {
    doc_id: string;
    timestamp: string;
    stages: {
      classification: {
        classification: 'C0' | 'C1' | 'C2' | 'C3';
        confidence: number;
        confidence_factors?: { agreement: number; evidence: number };
        confidence_explanation?: string;
        llm_raw_confidence?: number | null;
        method: string;
        llm_classification: string;
        rules_classification: string | null;
        agreement: boolean;
        reasoning: string;
        triggers: string[];
      };
      encryption: {
        encrypted: boolean;
        algorithm?: string;
        reason?: string;
        key_id?: string;
        ciphertext?: string;
      };
      storage: {
        path: string | null;
        stored: boolean;
        storage_path?: string;
      };
      access?: {
        user_id: string;
        granted: boolean;
        reason?: string;
        decrypted?: boolean;
      };
      audit: {
        total_events: number;
        chain_valid: boolean;
      };
    };
  };
}

export async function classifyDocumentWithSteps(
  text: string,
  docId?: string,
  userId?: string,
  settings?: Partial<ClassificationSettings>
): Promise<PipelineStepsResult> {
  const response = await fetch(`${API_BASE}/api/classify/steps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      doc_id: docId || `DOC_${Date.now()}`,
      text,
      user_id: userId,
      settings: settings ?? undefined,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error || 'Classification failed');
  }
  return response.json();
}

export async function classifyPDFWithSteps(
  file: File,
  docId?: string,
  userId?: string
): Promise<PipelineStepsResult> {
  const formData = new FormData();
  formData.append('file', file);
  if (docId) formData.append('doc_id', docId);
  if (userId) formData.append('user_id', userId);
  const response = await fetch(`${API_BASE}/api/classify/pdf/steps`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error || 'PDF classification failed');
  }
  return response.json();
}

// Classify multiple documents
export async function classifyBatch(
  documents: Array<{ doc_id?: string; text: string; user_id?: string }>
): Promise<{ success: boolean; processed: number; results: ClassificationResult[] }> {
  const response = await fetch(`${API_BASE}/api/classify/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ documents }),
  });

  if (!response.ok) {
    throw new Error('Batch classification failed');
  }

  return response.json();
}

// Get statistics
export async function getStatistics(): Promise<Statistics> {
  const response = await fetch(`${API_BASE}/api/statistics`);
  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to fetch statistics');
  }

  return data.statistics;
}

// Get users
export async function getUsers(): Promise<User[]> {
  const response = await fetch(`${API_BASE}/api/users`);
  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to fetch users');
  }

  return data.users;
}

// Get stored documents
export async function getDocuments(): Promise<StoredDocument[]> {
  const response = await fetch(`${API_BASE}/api/documents`);
  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to fetch documents');
  }

  return data.documents;
}

// Get digital signature system status
export async function getSignatureStatus(): Promise<{
  key_id: string;
  algorithm: string;
  standard: string;
  security_level: string;
  total_signed: number;
  signed_documents: string[];
  key_created_at: string;
}> {
  const response = await fetch(`${API_BASE}/api/signature-status`);
  const data = await response.json();
  if (!data.success) throw new Error('Failed to fetch signature status');
  return data.signature_status;
}

// Get audit logs
export async function getAuditLogs(): Promise<{
  logs: AuditLog[];
  chain_valid: boolean;
  count: number;
}> {
  const response = await fetch(`${API_BASE}/api/audit-logs`);
  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to fetch audit logs');
  }

  return {
    logs: data.logs,
    chain_valid: data.chain_valid,
    count: data.count,
  };
}

// Get sample documents
export async function getSampleDocuments(count: number = 5): Promise<SampleDocument[]> {
  const response = await fetch(`${API_BASE}/api/sample-documents?count=${count}`);
  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to fetch sample documents');
  }

  return data.documents;
}

// Get backend settings
export async function getBackendSettings(): Promise<ClassificationSettings> {
  const response = await fetch(`${API_BASE}/api/settings`);
  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to fetch settings');
  }

  return data.settings;
}

// Update backend settings
export async function updateBackendSettings(
  settings: Partial<ClassificationSettings>
): Promise<ClassificationSettings> {
  const response = await fetch(`${API_BASE}/api/settings`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(settings),
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error('Failed to update settings');
  }

  return data.settings;
}

// Get a single document
export async function getDocument(docId: string): Promise<{
  doc_id: string;
  classification: 'C0' | 'C1' | 'C2' | 'C3';
  timestamp: string;
  encrypted: boolean;
  content: string;
  metadata: Record<string, unknown>;
}> {
  const response = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(docId)}`);
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch document');
  }

  return data.document;
}

// Download a document's OCR/extracted text
export async function downloadDocument(docId: string, userId?: string): Promise<void> {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  const response = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(docId)}/download${params}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Download failed');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${docId}_ocr.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// Download the original file with a classification watermark (used in History)
export async function downloadTextWatermarked(docId: string, userId?: string): Promise<void> {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  const response = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(docId)}/download-text-watermarked${params}`,
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error((error as { error?: string }).error || 'Watermark download failed');
  }

  // Use the filename the server provides (preserves original extension: .jpg, .pdf, etc.)
  const disposition = response.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `${docId}_watermarked.pdf`;

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// Download the original file (PDF or image) with a classification watermark
export async function downloadWatermarkedFile(docId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(docId)}/download-watermarked`,
    { method: 'POST', body: formData },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error((error as { error?: string }).error || 'Watermark download failed');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const ext = file.name.includes('.') ? file.name.split('.').pop() : 'bin';
  a.download = `${docId}_watermarked.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// Dataset generation interfaces
export interface DatasetInfo {
  exists: boolean;
  count?: number;
  distribution?: Record<string, number>;
  formats?: string[];
  lastModified?: string;
  message?: string;
}

export interface GenerateDatasetResult {
  success: boolean;
  message: string;
  count: number;
  distribution: Record<string, number>;
  file: string;
  features: string[];
}

// Get dataset info
export async function getDatasetInfo(): Promise<DatasetInfo> {
  const response = await fetch(`${API_BASE}/api/dataset-info`);
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch dataset info');
  }

  return data;
}

// Generate new diverse dataset
export async function generateDataset(count: number = 100): Promise<GenerateDatasetResult> {
  const response = await fetch(`${API_BASE}/api/generate-dataset`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ count }),
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Failed to generate dataset');
  }

  return data;
}

// Evaluation result interfaces
export interface EvaluationMetrics {
  precision: number;
  recall: number;
  f1: number;
  support: number;
  tp: number;
  fp: number;
  fn: number;
}

export interface EvaluationResult {
  success: boolean;
  total_docs: number;
  accuracy: number;
  metrics: Record<string, EvaluationMetrics>;
  confusion_matrix: Record<string, Record<string, number>>;
  details: Array<{
    doc_id: string;
    true_label: string;
    pred_label: string;
    correct: boolean;
    confidence: number;
    method: string;
  }>;
}

// Run evaluation on test dataset
export async function runEvaluation(maxDocs: number = 50): Promise<EvaluationResult> {
  const response = await fetch(`${API_BASE}/api/evaluate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ max_docs: maxDocs }),
  });

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || 'Failed to run evaluation');
  }

  return data;
}

// Blockchain Audit Trail interfaces
export interface BlockchainBlock {
  index: number;
  timestamp: string;
  events: Array<{
    event_id: string;
    event_type: string;
    timestamp: string;
    data: Record<string, unknown>;
    hash: string;
  }>;
  events_count: number;
  merkle_root: string;
  previous_hash: string;
  hash: string;
  nonce: number;
  difficulty: number;
  block_signature: string | null;
}

export interface BlockchainStatus {
  chain_length: number;
  total_events: number;
  pending_events: number;
  difficulty: number;
  last_block_hash: string | null;
  last_block_time: string | null;
  chain_valid: boolean;
  algorithm: string;
  consensus: string;
}

export interface BlockchainVerification {
  valid: boolean;
  blocks_verified: number;
  invalid_blocks: number[];
  errors: string[];
}

export interface BlockchainAuditResult {
  success: boolean;
  blockchain: {
    status: BlockchainStatus;
    verification: BlockchainVerification;
    blocks: BlockchainBlock[];
  };
  legacy: {
    verification: {
      valid: boolean;
      total_logs: number;
      verified_logs: number;
      tampered_logs: string[];
      broken_chains: number[];
    };
    total_logs: number;
  };
}

// Get blockchain audit trail (Level 5 only)
export async function getBlockchainAudit(userId: string): Promise<BlockchainAuditResult> {
  const response = await fetch(`${API_BASE}/api/blockchain-audit?user_id=${encodeURIComponent(userId)}`);
  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || data.message || 'Failed to fetch blockchain audit trail');
  }

  return data;
}

// Force mine pending events into a new block (Level 5 only)
export async function mineBlock(userId: string): Promise<{ success: boolean; message: string; block?: BlockchainBlock }> {
  const response = await fetch(`${API_BASE}/api/blockchain-audit/mine`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_id: userId }),
  });

  const data = await response.json();

  if (!data.success && data.error) {
    throw new Error(data.error || data.message || 'Failed to mine block');
  }

  return data;
}
