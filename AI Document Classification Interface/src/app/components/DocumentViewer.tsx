import { useState, useEffect } from 'react';
import { X, FileText, Shield, Lock, Clock, User, AlertCircle, CheckCircle, Download, Eye, Loader2 } from 'lucide-react';
import { SecurityBadge } from './SecurityBadge';
import { useAuth } from '../context/AuthContext';
import { downloadDocument } from '../services/api';

interface DocumentData {
  doc_id: string;
  classification: 'C0' | 'C1' | 'C2' | 'C3';
  timestamp: string;
  content?: string;
  encrypted?: boolean;
  original_filename?: string;
  redacted_fields?: string[];
  metadata?: {
    text_length: number;
    classification_method: string;
    triggers: string[];
    reasoning?: string;
    confidence?: number;
    confidence_factors?: {
      agreement: number;
      evidence: number;
    };
    confidence_explanation?: string;
    llm_classification?: string;
    rules_classification?: string | null;
    agreement?: boolean;
    llm_raw_confidence?: number;
  };
}

interface DocumentViewerProps {
  docId: string;
  onClose: () => void;
}

const canDownloadDocument = (userLevel: number, classification: string): boolean => {
  switch (classification) {
    case 'C0': return userLevel >= 1;
    case 'C1': return userLevel >= 2;
    case 'C2': return userLevel >= 4;
    case 'C3': return userLevel >= 5;
    default:   return false;
  }
};

export function DocumentViewer({ docId, onClose }: DocumentViewerProps) {
  const { user } = useAuth();
  const [document, setDocument] = useState<DocumentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accessGranted, setAccessGranted] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadDocument(docId, user?.user_id);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Failed to download document. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  useEffect(() => {
    const fetchDocument = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`http://127.0.0.1:5001/api/documents/${docId}?user_id=${user?.user_id}`);

        if (!response.ok) {
          // Try to get error message from response
          const errorData = await response.json().catch(() => null);
          if (errorData && errorData.message) {
            setError(errorData.message);
          } else if (response.status === 403) {
            setError('Access denied: You do not have permission to view this document');
          } else if (response.status === 404) {
            setError('Document not found');
          } else {
            setError(`Failed to load document (${response.status})`);
          }
          return;
        }

        const data = await response.json();

        if (!data.success) {
          setError(data.error || 'Failed to load document');
          return;
        }

        // API returns {success: true, document: {...}}
        const doc = data.document;
        setDocument(doc);

        // Access is already checked by the backend, but we still track it for UI
        setAccessGranted(true);

      } catch (err) {
        console.error('Error loading document:', err);
        setError('Failed to connect to server. Please make sure the backend is running.');
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [docId, user]);

  const getClassificationInfo = (classification: string) => {
    const info: Record<string, { label: string; description: string; requiredLevel: number }> = {
      C0: { label: 'Public', description: 'Publicly available information', requiredLevel: 1 },
      C1: { label: 'Internal', description: 'Internal use only', requiredLevel: 2 },
      C2: { label: 'Confidential', description: 'Confidential business information', requiredLevel: 3 },
      C3: { label: 'Highly Sensitive', description: 'Highly sensitive data requiring maximum protection', requiredLevel: 4 },
    };
    return info[classification] || info['C0'];
  };

  const previewUrl = `http://127.0.0.1:5001/api/documents/${docId}/preview-file?user_id=${user?.user_id ?? ''}#toolbar=0&navpanes=0&scrollbar=0`;

  return (
    <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center px-6">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full flex flex-col mt-28" style={{ maxWidth: '1200px', maxHeight: 'calc(100vh - 8rem)' }}>
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#1E3A8A] to-[#0891B2] flex items-center justify-center">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Document Details</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">{docId}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          {loading ? (
            <div className="flex flex-col items-center justify-center w-full py-12">
              <Loader2 className="w-8 h-8 text-[#0891B2] animate-spin mb-4" />
              <p className="text-gray-500 dark:text-gray-400">Loading document...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center w-full py-12">
              <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
              <p className="text-red-600 dark:text-red-400">{error}</p>
            </div>
          ) : document ? (
            <>
            {/* Left: File Preview or Redacted Text */}
            {accessGranted && (
              <div className="flex-1 bg-gray-100 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col min-h-0">
                <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex items-center gap-2">
                  <Eye className="w-4 h-4 text-gray-400" />
                  <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">
                    {document.redacted_fields && document.redacted_fields.length > 0 ? 'Redacted Content' : 'Document Preview'}
                  </span>
                  {document.redacted_fields && document.redacted_fields.length > 0 && (
                    <span className="ml-auto text-xs px-2 py-0.5 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 rounded-full">
                      {document.redacted_fields.length} field(s) redacted
                    </span>
                  )}
                </div>
                <div className="flex-1 overflow-auto">
                  {document.redacted_fields && document.redacted_fields.length > 0 ? (
                    // Show redacted text — never show original file when content is redacted
                    <div className="p-6">
                      <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed font-mono">
                        {document.content ?? 'Content not available.'}
                      </p>
                    </div>
                  ) : (
                    // Full access — show original file
                    <iframe
                      src={previewUrl}
                      className="w-full h-full border-0"
                      title="Document Preview"
                    />
                  )}
                </div>
              </div>
            )}

            {/* Right: Metadata */}
            <div className="w-80 flex-shrink-0 overflow-y-auto p-6 space-y-6">
              {/* Access Status */}
              <div className={`p-4 rounded-xl ${
                accessGranted
                  ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                  : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
              }`}>
                <div className="flex items-center gap-3">
                  {accessGranted ? (
                    <CheckCircle className="w-6 h-6 text-green-600 dark:text-green-400" />
                  ) : (
                    <AlertCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
                  )}
                  <div>
                    <p className={`font-medium ${accessGranted ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                      {accessGranted ? 'Access Granted' : 'Access Denied'}
                    </p>
                    <p className={`text-sm ${accessGranted ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {accessGranted
                        ? `Your access level (${user?.access_level}) permits viewing this document`
                        : `Your access level (${user?.access_level}) is insufficient for ${document.classification} documents`
                      }
                    </p>
                  </div>
                </div>
              </div>

              {/* Classification */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Classification</p>
                  <SecurityBadge level={document.classification} size="md" />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    {getClassificationInfo(document.classification).description}
                  </p>
                </div>

                <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Encryption Status</p>
                  <div className="flex items-center gap-2">
                    {document.encrypted ? (
                      <>
                        <Lock className="w-5 h-5 text-green-600" />
                        <span className="font-medium text-green-600 dark:text-green-400">Encrypted</span>
                      </>
                    ) : (
                      <>
                        <Shield className="w-5 h-5 text-gray-400" />
                        <span className="font-medium text-gray-600 dark:text-gray-400">Not Encrypted</span>
                      </>
                    )}
                  </div>
                  {document.encrypted && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      Kyber-768 + AES-256-GCM
                    </p>
                  )}
                </div>
              </div>

              {/* Details */}
              <div className="space-y-3">
                <div className="flex items-center justify-between py-3 border-b border-gray-200 dark:border-gray-700">
                  <span className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Timestamp
                  </span>
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {document.timestamp ? new Date(document.timestamp).toLocaleString() : 'N/A'}
                  </span>
                </div>

                {document.metadata && (
                  <>
                    <div className="flex items-center justify-between py-3 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-sm text-gray-500 dark:text-gray-400">Document Size</span>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {document.metadata.text_length} characters
                      </span>
                    </div>

                    <div className="flex items-center justify-between py-3 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-sm text-gray-500 dark:text-gray-400">Classification Method</span>
                      <span className="text-xs px-2 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
                        {document.metadata.classification_method}
                      </span>
                    </div>

                    {document.metadata.triggers && document.metadata.triggers.length > 0 && (
                      <div className="py-3">
                        <span className="text-sm text-gray-500 dark:text-gray-400 block mb-2">Detected Triggers</span>
                        <div className="flex flex-wrap gap-2">
                          {document.metadata.triggers.map((trigger, i) => (
                            <span key={i} className="text-xs px-2 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
                              {trigger}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* Detailed Classification Analysis - Level 5 Only */}
                {user && user.access_level >= 5 && document.metadata && (
                  <div className="p-4 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-200 dark:border-indigo-800">
                    <div className="flex items-center gap-2 mb-4">
                      <Shield className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                      <span className="font-semibold text-indigo-800 dark:text-indigo-300">Detailed Classification Analysis</span>
                      <span className="text-xs px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-full">Level 5 Only</span>
                    </div>

                    {/* LLM vs Rules Comparison */}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">LLM Classification (LLaMA 3)</p>
                        <p className="text-lg font-bold text-blue-700 dark:text-blue-400">
                          {document.metadata.llm_classification ?? 'N/A'}
                        </p>
                        {document.metadata.llm_raw_confidence != null && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Raw Confidence: {(document.metadata.llm_raw_confidence * 100).toFixed(0)}%
                          </p>
                        )}
                      </div>
                      <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Rules Classification</p>
                        <p className="text-lg font-bold text-amber-700 dark:text-amber-400">
                          {document.metadata.rules_classification ?? (document.metadata.triggers?.length ? document.classification : 'N/A')}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {document.metadata.triggers && document.metadata.triggers.length > 0
                            ? `${document.metadata.triggers.length} trigger(s) detected`
                            : 'No patterns matched'}
                        </p>
                      </div>
                    </div>

                    {/* Decision Method */}
                    <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-gray-500 dark:text-gray-400">Decision Method</span>
                        <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                          document.metadata.classification_method === 'AGREEMENT'
                            ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                            : document.metadata.classification_method === 'RULES_OVERRIDE'
                            ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                            : document.metadata.classification_method === 'RULES_ESCALATED'
                            ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
                            : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                        }`}>
                          {document.metadata.classification_method}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 dark:text-gray-400">Agreement:</span>
                        {document.metadata.agreement ? (
                          <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> LLM and Rules agree
                          </span>
                        ) : (
                          <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" /> Classifiers disagree
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Confidence Breakdown */}
                    {document.metadata.confidence != null && (
                      <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 mb-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs text-gray-500 dark:text-gray-400">Final Confidence</span>
                          <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
                            {(document.metadata.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        {document.metadata.confidence_factors && (
                          <div className="space-y-2 mt-3">
                            <div>
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-gray-500 dark:text-gray-400">Agreement Factor (Dietterich, 2000)</span>
                                <span className="font-medium text-gray-700 dark:text-gray-300">{(document.metadata.confidence_factors.agreement * 100).toFixed(0)}%</span>
                              </div>
                              <div className="h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                                <div className="h-full bg-green-500 rounded-full" style={{ width: `${document.metadata.confidence_factors.agreement * 100}%` }} />
                              </div>
                            </div>
                            <div>
                              <div className="flex items-center justify-between text-xs mb-1">
                                <span className="text-gray-500 dark:text-gray-400">Evidence Factor (Dempster-Shafer, 1967)</span>
                                <span className="font-medium text-gray-700 dark:text-gray-300">{(document.metadata.confidence_factors.evidence * 100).toFixed(0)}%</span>
                              </div>
                              <div className="h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-500 rounded-full" style={{ width: `${document.metadata.confidence_factors.evidence * 100}%` }} />
                              </div>
                            </div>
                            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                              Formula: 0.50 x Agreement + 0.50 x Evidence
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Reasoning */}
                    {document.metadata.reasoning && (
                      <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                        <span className="text-xs text-gray-500 dark:text-gray-400 block mb-2">AI Reasoning</span>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{document.metadata.reasoning}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Redaction notice */}
              {document.redacted_fields && document.redacted_fields.length > 0 && (
                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl">
                  <div className="flex items-start gap-2">
                    <Eye className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                        Some fields redacted based on your role
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {document.redacted_fields.map(f => (
                          <span key={f} className="text-xs px-2 py-0.5 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 rounded-full">
                            {f.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Document Preview (if access granted) */}
              {accessGranted && document.content && (
                <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Document Content</p>
                    <span className="text-xs text-gray-400">{document.content.length.toLocaleString()} characters</span>
                  </div>
                  <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-600 max-h-96 overflow-y-auto">
                    <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
                      {document.content}
                    </p>
                  </div>
                </div>
              )}

              {accessGranted && document.encrypted && (
                <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800">
                  <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
                    <Lock className="w-5 h-5" />
                    <span className="font-medium">Content Encrypted</span>
                  </div>
                  <p className="text-sm text-amber-600 dark:text-amber-400 mt-1">
                    This document is protected with post-quantum encryption (Kyber-768 + AES-256-GCM).
                    Content can only be decrypted through the secure pipeline.
                  </p>
                </div>
              )}
            </div>
            </>
          ) : null}
        </div>

        {/* Footer Actions */}
        <div className="p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <User className="w-4 h-4" />
              Viewing as: {user?.name} (Level {user?.access_level})
            </div>
            <div className="flex items-center gap-3">
              {accessGranted && canDownloadDocument(user?.access_level ?? 0, document?.classification ?? '') && (
                <button
                  onClick={handleDownload}
                  disabled={downloading}
                  className="flex items-center gap-2 px-4 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-colors disabled:opacity-50"
                >
                  {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  {downloading ? 'Downloading...' : 'Download'}
                </button>
              )}
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
