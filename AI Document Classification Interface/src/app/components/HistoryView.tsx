import { useState, useEffect, useMemo, Fragment } from 'react';
import { Search, Download, Eye, CheckCircle, XCircle, ChevronLeft, ChevronRight, ChevronDown, RefreshCw, AlertCircle, Loader2, Shield, Brain, ScrollText, Building2, User, ShieldAlert, Flag, CheckCheck, RotateCcw, Pencil, AlertTriangle, Lock } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Textarea } from './ui/textarea';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from './ui/select';
import { SecurityBadge } from './SecurityBadge';
import { DocumentViewer } from './DocumentViewer';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { getDocuments, getAuditLogs, downloadDocument, downloadTextWatermarked, flagDocument, resolveFlag, cisoOverride, getFlaggedDocuments, type StoredDocument, type AuditLog, type FlagInfo } from '../services/api';

// Access level required for each classification
// C3: L3+ (own department, with heavy redaction) — actual enforcement is server-side
const classificationAccessLevel: Record<string, number> = {
  'C0': 1, 'C1': 2, 'C2': 3, 'C3': 3,
};

const canAccessDocument = (userLevel: number, classification: string): boolean =>
  userLevel >= (classificationAccessLevel[classification] || 1);

const canDownloadDocument = (userLevel: number, classification: string): boolean => {
  // Download follows the same access rules as viewing
  switch (classification) {
    case 'C0': return userLevel >= 1;
    case 'C1': return userLevel >= 2;
    case 'C2': return userLevel >= 3;
    case 'C3': return userLevel >= 3;
    default:   return false;
  }
};


interface Document {
  id: string;
  name: string;
  classification: 'C0' | 'C1' | 'C2' | 'C3';
  confidence: number;
  method: string;
  llmResult: string;
  rulesResult: string;
  agreement: boolean;
  timestamp: string;
  rawTimestamp: number;
  encrypted: boolean;
  reasoning: string;
  triggers: string[];
  cdeDetected: string[];
  documentType?: string;
  department?: string;
  uploadedBy?: string;
  tampered?: boolean;
  tamperWarning?: string;
  flag?: FlagInfo | null;
}

export function HistoryView({ onViewChange: _onViewChange }: { onViewChange?: (view: string) => void }) {
  const { user } = useAuth();
  const { t, isRTL } = useSettings();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [filterEncrypted, setFilterEncrypted] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('date-desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
  const [downloadingDoc, setDownloadingDoc] = useState<string | null>(null);
  const [downloadingWatermark, setDownloadingWatermark] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const itemsPerPage = 10;

  // Flag dialog state
  const [flagDocId, setFlagDocId]           = useState<string | null>(null);
  const [flagComment, setFlagComment]       = useState('');
  const [flagSuggested, setFlagSuggested]   = useState('');
  const [flagSubmitting, setFlagSubmitting] = useState(false);

  // CISO resolve dialog state (for flagged docs)
  const [resolveDocId, setResolveDocId]         = useState<string | null>(null);
  const [resolveAction, setResolveAction]       = useState<'MAINTAIN' | 'OVERRIDE'>('MAINTAIN');
  const [resolveComment, setResolveComment]     = useState('');
  const [resolveOverride, setResolveOverride]   = useState('');
  const [resolveSubmitting, setResolveSubmitting] = useState(false);

  // CISO direct override dialog state (any document)
  const [editDocId, setEditDocId]           = useState<string | null>(null);
  const [editNewClass, setEditNewClass]     = useState('');
  const [editReasoning, setEditReasoning]   = useState('');
  const [editSubmitting, setEditSubmitting] = useState(false);

  // CISO Flagged Documents panel state
  const [showFlaggedPanel, setShowFlaggedPanel]   = useState(false);
  const [flaggedDocs, setFlaggedDocs]             = useState<Array<{
    doc_id: string; original_filename: string | null; classification: string;
    timestamp: string; department: string | null; document_type: string | null; flag: FlagInfo;
  }>>([]);
  const [flaggedLoading, setFlaggedLoading]       = useState(false);
  const [flaggedFilter, setFlaggedFilter]         = useState<'PENDING' | 'RESOLVED'>('PENDING');

  const userLevel = user?.access_level || 1;
  const isLevel5 = userLevel >= 5;
  const isDPO = user?.role === 'DPO';

  const toggleRow = (docId: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(docId) ? next.delete(docId) : next.add(docId);
      return next;
    });
  };

  const handleDownload = async (docId: string) => {
    setDownloadingDoc(docId);
    try { await downloadDocument(docId, user?.user_id); }
    catch { alert('Failed to download document. Please try again.'); }
    finally { setDownloadingDoc(null); }
  };

  const handleDownloadWatermarked = async (docId: string) => {
    setDownloadingWatermark(docId);
    try { await downloadTextWatermarked(docId, user?.user_id); }
    catch { alert('Failed to download watermarked document. Please try again.'); }
    finally { setDownloadingWatermark(null); }
  };

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const [storedDocs, auditData] = await Promise.all([getDocuments(user?.user_id), getAuditLogs()]);

      const auditMap = new Map<string, AuditLog>();
      auditData.logs.forEach(log => {
        if (log.event_type === 'DOCUMENT_CLASSIFIED') {
          const docId = (log.data as { document_id?: string }).document_id;
          if (docId) auditMap.set(docId, log);
        }
      });

      const docs: Document[] = storedDocs
        .filter((doc) => doc?.doc_id)
        .map((doc: StoredDocument) => {
          const auditLog = auditMap.get(doc.doc_id);
          const method = doc.method || (auditLog?.data as { method?: string })?.method || 'AGREEMENT';
          const docDate = new Date(doc.timestamp);
          return {
            id: doc.doc_id,
            name: doc.original_filename || doc.doc_id,
            classification: doc.classification,
            confidence: doc.confidence ?? 0.95,
            method,
            llmResult: doc.llm_classification || doc.classification,
            rulesResult: doc.rules_classification || 'None',
            agreement: method === 'AGREEMENT',
            timestamp: docDate.toLocaleString(),
            rawTimestamp: docDate.getTime(),
            encrypted: doc.encrypted,
            reasoning: doc.reasoning || doc.ai_reasoning || '',
            triggers: doc.triggers || [],
            cdeDetected: doc.cde_detected || [],
            documentType: doc.document_type,
            department: doc.department ?? undefined,
            uploadedBy: doc.uploaded_by ?? undefined,
            // Only flag as tampered if there is an actual hash mismatch warning.
            // "not found in protection chain" means unprotected — not tampered.
            tampered: doc.integrity_check?.verified === false && !!doc.integrity_check?.warning,
            tamperWarning: doc.integrity_check?.warning ?? undefined,
            flag: doc.flag ?? null,
          };
        });

      setDocuments(docs);
    } catch {
      setError('Failed to load documents. Is the API server running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocuments(); }, []);

  const openFlagDialog = (docId: string) => {
    setFlagDocId(docId);
    setFlagComment('');
    setFlagSuggested('');
  };

  const handleFlagSubmit = async () => {
    if (!flagDocId || !flagComment.trim()) return;
    setFlagSubmitting(true);
    try {
      await flagDocument(flagDocId, {
        flagged_by_id: user?.user_id || 'anonymous',
        flagged_by_name: user?.name || 'Anonymous',
        comment: flagComment.trim(),
        suggested_classification: (flagSuggested && flagSuggested !== 'none' ? flagSuggested : null) as 'C0' | 'C1' | 'C2' | 'C3' | null,
      });
      setFlagDocId(null);
      await fetchDocuments();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to flag document');
    } finally {
      setFlagSubmitting(false);
    }
  };

  const openEditDialog = (docId: string) => {
    setEditDocId(docId);
    setEditNewClass('');
    setEditReasoning('');
  };

  const handleEditSubmit = async () => {
    if (!editDocId || !editNewClass || !editReasoning.trim()) return;
    setEditSubmitting(true);
    try {
      await cisoOverride(editDocId, {
        overridden_by_id: user?.user_id || 'unknown',
        overridden_by_name: user?.name || 'CISO',
        new_classification: editNewClass as 'C0' | 'C1' | 'C2' | 'C3',
        reasoning: editReasoning.trim(),
      });
      setEditDocId(null);
      await fetchDocuments();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to override classification');
    } finally {
      setEditSubmitting(false);
    }
  };

  const loadFlaggedDocs = async (status: 'PENDING' | 'RESOLVED') => {
    setFlaggedLoading(true);
    try {
      const data = await getFlaggedDocuments(status, user?.user_id);
      setFlaggedDocs(data.documents);
    } catch {
      setFlaggedDocs([]);
    } finally {
      setFlaggedLoading(false);
    }
  };

  const openFlaggedPanel = () => {
    setShowFlaggedPanel(true);
    loadFlaggedDocs('PENDING');
  };

  const openResolveDialog = (docId: string) => {
    setResolveDocId(docId);
    setResolveAction('MAINTAIN');
    setResolveComment('');
    setResolveOverride('');
  };

  const handleResolveSubmit = async () => {
    if (!resolveDocId || !resolveComment.trim()) return;
    if (resolveAction === 'OVERRIDE' && !resolveOverride) {
      alert('Please select an override classification');
      return;
    }
    setResolveSubmitting(true);
    try {
      await resolveFlag(resolveDocId, {
        resolved_by_id: user?.user_id || 'unknown',
        resolved_by_name: user?.name || 'DPO',
        action: resolveAction,
        comment: resolveComment.trim(),
        override_classification: resolveAction === 'OVERRIDE'
          ? (resolveOverride as 'C0' | 'C1' | 'C2' | 'C3')
          : null,
      });
      setResolveDocId(null);
      await fetchDocuments();
      if (showFlaggedPanel) loadFlaggedDocs(flaggedFilter);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to resolve flag');
    } finally {
      setResolveSubmitting(false);
    }
  };

  const accessibleDocuments = documents.filter(doc => canAccessDocument(userLevel, doc.classification));
  const classificationOrder: Record<string, number> = { 'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3 };

  const filteredDocuments = useMemo(() => {
    const filtered = accessibleDocuments.filter((doc) => {
      const matchesSearch =
        doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (doc.documentType || '').toLowerCase().includes(searchTerm.toLowerCase());
      const matchesLevel    = filterLevel === 'all' || doc.classification === filterLevel;
      const matchesEncrypted = filterEncrypted === 'all' ||
        (filterEncrypted === 'yes' && doc.encrypted) ||
        (filterEncrypted === 'no' && !doc.encrypted);
      return matchesSearch && matchesLevel && matchesEncrypted;
    });

    return [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'date-desc': return b.rawTimestamp - a.rawTimestamp;
        case 'date-asc':  return a.rawTimestamp - b.rawTimestamp;
        case 'class-desc': return classificationOrder[b.classification] - classificationOrder[a.classification];
        case 'class-asc':  return classificationOrder[a.classification] - classificationOrder[b.classification];
        case 'name-asc':  return a.name.localeCompare(b.name);
        case 'name-desc': return b.name.localeCompare(a.name);
        default: return 0;
      }
    });
  }, [accessibleDocuments, searchTerm, filterLevel, filterEncrypted, sortBy]);

  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedDocuments = filteredDocuments.slice(startIndex, startIndex + itemsPerPage);

  const exportToCsv = () => {
    const headers = (isLevel5 || isDPO)
      ? ['ID', 'Filename', 'Classification', 'Method', 'LLM Result', 'Rules Result', 'Confidence', 'Triggers', 'Reasoning', 'Encrypted', 'Timestamp']
      : ['ID', 'Filename', 'Classification', 'Method', 'Encrypted', 'Timestamp'];

    const rows = filteredDocuments.map(doc => {
      if (isLevel5 || isDPO) {
        return [
          doc.id, doc.name, doc.classification, doc.method,
          doc.llmResult, doc.rulesResult,
          `${(doc.confidence * 100).toFixed(0)}%`,
          doc.triggers.join('; '),
          `"${(doc.reasoning || '').replace(/"/g, '""')}"`,
          doc.encrypted ? 'Yes' : 'No', doc.timestamp,
        ];
      }
      return [doc.id, doc.name, doc.classification, doc.method, doc.encrypted ? 'Yes' : 'No', doc.timestamp];
    });

    const csvContent = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `classification_history_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-red-800 dark:text-red-300 mb-2">Connection Error</h3>
          <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
          <button onClick={fetchDocuments} className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-6 ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('history.title')}</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t('history.showing')} {accessibleDocuments.length} {t('history.documents')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* DPO — Flagged Documents button with pending count badge */}
          {isDPO && (() => {
            const pendingCount = documents.filter(d => d.flag?.status === 'PENDING').length;
            return (
              <button
                onClick={openFlaggedPanel}
                className="relative flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-all"
              >
                <Flag className="w-4 h-4" />
                Flagged Documents
                {pendingCount > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 flex items-center justify-center w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full">
                    {pendingCount}
                  </span>
                )}
              </button>
            );
          })()}
          <button
            onClick={fetchDocuments}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {t('dashboard.refresh')}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="flex flex-col lg:flex-row gap-3 flex-wrap">
          {/* Search */}
          <div className="flex-1 min-w-48">
            <div className="relative">
              <Search className={`absolute ${isRTL ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400`} />
              <input
                type="text"
                placeholder={t('history.search')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={`w-full ${isRTL ? 'pr-10 pl-4' : 'pl-10 pr-4'} py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400`}
              />
            </div>
          </div>

          {/* Classification filter */}
          <div className="w-full lg:w-44">
            <select value={filterLevel} onChange={(e) => setFilterLevel(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100">
              <option value="all">{t('history.allLevels')}</option>
              <option value="C0">C0 — Public</option>
              <option value="C1">C1 — Internal</option>
              <option value="C2">C2 — Confidential</option>
              <option value="C3">C3 — Highly Sensitive</option>
            </select>
          </div>

          {/* Encrypted filter */}
          <div className="w-full lg:w-40">
            <select value={filterEncrypted} onChange={(e) => setFilterEncrypted(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100">
              <option value="all">{t('history.allDocuments')}</option>
              <option value="yes">{t('history.encryptedOnly')}</option>
              <option value="no">{t('history.notEncrypted')}</option>
            </select>
          </div>

          {/* Sort */}
          <div className="w-full lg:w-52">
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100">
              <option value="date-desc">Date (Newest First)</option>
              <option value="date-asc">Date (Oldest First)</option>
              <option value="class-desc">Classification (C3→C0)</option>
              <option value="class-asc">Classification (C0→C3)</option>
              <option value="name-asc">Name (A→Z)</option>
              <option value="name-desc">Name (Z→A)</option>
            </select>
          </div>

          <button onClick={exportToCsv} disabled={filteredDocuments.length === 0}
            className="px-4 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-all flex items-center gap-2 whitespace-nowrap disabled:opacity-50">
            <Download className="w-4 h-4" />
            {t('history.exportCSV')}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-gray-400">
              {documents.length === 0 ? t('history.noDocuments') : t('history.noMatches')}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Document</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Classification</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('history.method')}</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('history.encrypted')}</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('history.timestamp')}</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('history.actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {paginatedDocuments.map((doc) => (
                    <Fragment key={doc.id}>
                      <tr
                        className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer"
                        onClick={() => toggleRow(doc.id)}
                      >
                        {/* Document name */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-1.5">
                            {/* Flag button — L2+ only, left of name, hidden for L1 Viewers and CISO, hidden if pending flag exists */}
                            {userLevel >= 2 && !isLevel5 && doc.flag?.status !== 'PENDING' && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); openFlagDialog(doc.id); }}
                                    className="flex-shrink-0 p-1 hover:bg-amber-100 dark:hover:bg-amber-900/30 rounded transition-colors"
                                  >
                                    <Flag className="w-3.5 h-3.5 text-amber-400" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="top">Flag as misclassified</TooltipContent>
                              </Tooltip>
                            )}

                            {/* Collapse chevron */}
                            <span className="flex-shrink-0 text-gray-400">
                              {expandedRows.has(doc.id) ? <ChevronDown className="w-4 h-4" /> : <ChevronDown className="w-4 h-4 -rotate-90" />}
                            </span>

                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5">
                                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-48" title={doc.name}>
                                  {doc.name}
                                </div>
                                {doc.tampered && (
                                  <Tooltip>
                                    <TooltipTrigger>
                                      <ShieldAlert className="w-4 h-4 text-red-600 flex-shrink-0" />
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      <p className="text-xs max-w-xs">{doc.tamperWarning || 'TAMPERING DETECTED: Document metadata has been modified.'}</p>
                                    </TooltipContent>
                                  </Tooltip>
                                )}
                              </div>
                              <div className="text-xs text-gray-400 dark:text-gray-500 truncate max-w-48">{doc.id}</div>
                            </div>
                          </div>
                        </td>

                        {/* Classification */}
                        <td className="px-6 py-4 whitespace-nowrap">
                          <SecurityBadge level={doc.classification} size="sm" />
                          {doc.tampered && (
                            <div className="mt-1 text-xs text-red-600 dark:text-red-400 font-semibold">TAMPERED</div>
                          )}
                          {doc.flag?.status === 'PENDING' && (
                            <div className="mt-1">
                              <Badge className="text-xs bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700">
                                FLAGGED
                              </Badge>
                            </div>
                          )}
                          {doc.flag?.status === 'RESOLVED' && (
                            <div className="mt-1">
                              <Badge className="text-xs bg-emerald-100 text-emerald-800 border border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700">
                                {doc.flag.resolution_action === 'OVERRIDE' ? 'OVERRIDDEN' : 'REVIEWED'}
                              </Badge>
                            </div>
                          )}
                        </td>

                        {/* Method */}
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            doc.method === 'AGREEMENT'      ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                            doc.method === 'RULES_OVERRIDE' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400' :
                                                              'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                          }`}>
                            {doc.method.replace(/_/g, ' ')}
                          </span>
                        </td>

                        {/* Encrypted */}
                        <td className="px-6 py-4 whitespace-nowrap">
                          {doc.encrypted
                            ? <CheckCircle className="w-5 h-5 text-[#10B981]" />
                            : <XCircle className="w-5 h-5 text-gray-400" />}
                        </td>

                        {/* Timestamp */}
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                          {doc.timestamp}
                        </td>

                        {/* Actions */}
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            {/* Document is PENDING review — lock access for regular users */}
                            {doc.flag?.status === 'PENDING' && !isLevel5 && !isDPO ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-amber-600 dark:text-amber-400 text-xs font-medium cursor-not-allowed">
                                    <Lock className="w-3.5 h-3.5" />
                                    Under Review
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent side="top">This document is locked pending DPO review</TooltipContent>
                              </Tooltip>
                            ) : (
                              <>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button onClick={() => setSelectedDocument(doc.id)}
                                  className="p-1 hover:bg-gray-100 dark:hover:bg-gray-600 rounded transition-colors">
                                  <Eye className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">View document</TooltipContent>
                            </Tooltip>

                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  onClick={() => canDownloadDocument(userLevel, doc.classification) && handleDownload(doc.id)}
                                  disabled={downloadingDoc === doc.id || !canDownloadDocument(userLevel, doc.classification)}
                                  className={`p-1 rounded transition-colors ${canDownloadDocument(userLevel, doc.classification) ? 'hover:bg-blue-100 dark:hover:bg-blue-900/30' : 'opacity-30 cursor-not-allowed'}`}>
                                  {downloadingDoc === doc.id ? <Loader2 className="w-4 h-4 text-blue-600 animate-spin" /> : <ScrollText className="w-4 h-4 text-blue-600 dark:text-blue-400" />}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                {canDownloadDocument(userLevel, doc.classification) ? 'Download OCR text (.txt)' : 'Download restricted'}
                              </TooltipContent>
                            </Tooltip>

                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  onClick={() => canDownloadDocument(userLevel, doc.classification) && handleDownloadWatermarked(doc.id)}
                                  disabled={downloadingWatermark === doc.id || !canDownloadDocument(userLevel, doc.classification)}
                                  className={`p-1 rounded transition-colors ${canDownloadDocument(userLevel, doc.classification) ? 'hover:bg-indigo-100 dark:hover:bg-indigo-900/30' : 'opacity-30 cursor-not-allowed'}`}>
                                  {downloadingWatermark === doc.id ? <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" /> : <Download className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                {canDownloadDocument(userLevel, doc.classification) ? 'Download with watermark' : 'Download restricted'}
                              </TooltipContent>
                            </Tooltip>
                              </>
                            )}

                            {/* CISO/DPO Edit button — override any document's classification */}
                            {(isLevel5 || isDPO) && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    onClick={() => openEditDialog(doc.id)}
                                    className="p-1 hover:bg-violet-100 dark:hover:bg-violet-900/30 rounded transition-colors"
                                  >
                                    <Pencil className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="top">Override classification</TooltipContent>
                              </Tooltip>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Expanded detail row — available to all users */}
                      {expandedRows.has(doc.id) && (
                        <tr>
                          <td colSpan={6} className="px-6 py-0 bg-gray-50/60 dark:bg-gray-700/20">
                            <div className="py-4 pl-6 border-l-4 border-indigo-300 dark:border-indigo-600 ml-2 mb-2">

                              {/* Tamper warning banner */}
                              {doc.tampered && (
                                <div className="mb-4 flex items-start gap-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded-lg">
                                  <ShieldAlert className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                                  <div>
                                    <p className="text-sm font-bold text-red-700 dark:text-red-300">Integrity Violation Detected</p>
                                    <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{doc.tamperWarning || 'Document metadata has been modified since it was protected.'}</p>
                                  </div>
                                </div>
                              )}

                              {/* Meta row: uploader, dept */}
                              <div className="flex flex-wrap gap-3 mb-4 text-xs text-gray-600 dark:text-gray-400">
                                {doc.uploadedBy && (
                                  <span className="flex items-center gap-1">
                                    <User className="w-3 h-3" />
                                    Uploaded by <strong className="text-gray-800 dark:text-gray-200 ml-1">{doc.uploadedBy}</strong>
                                  </span>
                                )}
                                {doc.department && (
                                  <span className="flex items-center gap-1">
                                    <Building2 className="w-3 h-3" />
                                    <strong className="text-gray-800 dark:text-gray-200">{doc.department}</strong>
                                  </span>
                                )}
                              </div>

                              {/* L5/DPO classification analysis */}
                              {(isLevel5 || isDPO) && (
                                <>
                                  <div className="flex items-center gap-2 mb-3">
                                    <Shield className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                                    <span className="text-sm font-semibold text-indigo-800 dark:text-indigo-300">Classification Analysis</span>
                                    <span className="text-xs px-1.5 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded">Admin</span>
                                  </div>
                                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
                                    <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                                      <div className="flex items-center gap-1.5 mb-2">
                                        <Brain className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                                        <span className="text-xs font-medium text-blue-700 dark:text-blue-400">LLM (LLaMA 3)</span>
                                      </div>
                                      <span className="text-lg font-bold text-blue-800 dark:text-blue-300">{doc.llmResult}</span>
                                    </div>
                                    <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                                      <div className="flex items-center gap-1.5 mb-2">
                                        <Shield className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                                        <span className="text-xs font-medium text-amber-700 dark:text-amber-400">Security Rules</span>
                                      </div>
                                      <span className="text-lg font-bold text-amber-800 dark:text-amber-300">
                                        {doc.rulesResult === 'None' || !doc.rulesResult ? 'No triggers' : doc.rulesResult}
                                      </span>
                                    </div>
                                    <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                                      <div className="flex items-center gap-1.5 mb-2">
                                        <ScrollText className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
                                        <span className="text-xs font-medium text-purple-700 dark:text-purple-400">Confidence</span>
                                      </div>
                                      <span className="text-lg font-bold text-purple-800 dark:text-purple-300">
                                        {`${(doc.confidence * 100).toFixed(0)}%`}
                                      </span>
                                    </div>
                                  </div>
                                  {doc.triggers && doc.triggers.length > 0 && (doc.classification === 'C2' || doc.classification === 'C3') && (
                                    <div className="mb-2">
                                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 mr-2">Rule Triggers:</span>
                                      {doc.triggers.map((trigger, idx) => (
                                        <span key={idx} className="inline-block text-xs px-2 py-0.5 mr-1 mb-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">{trigger}</span>
                                      ))}
                                    </div>
                                  )}
                                  {doc.cdeDetected && doc.cdeDetected.length > 0 && (doc.classification === 'C2' || doc.classification === 'C3') && (
                                    <div className="mb-3">
                                      <span className="text-xs font-medium text-red-500 dark:text-red-400 mr-2">CDEs Detected:</span>
                                      {doc.cdeDetected.map((cde, idx) => (
                                        <span key={idx} className="inline-block text-xs px-2 py-0.5 mr-1 mb-1 rounded-full bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 font-medium">⚠ {cde}</span>
                                      ))}
                                    </div>
                                  )}
                                </>
                              )}

                              {/* AI Reasoning — CISO and DPO (may contain PII from extracted text) */}
                              {(isLevel5 || isDPO) && doc.reasoning && (
                                <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
                                  <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1.5">🤖 AI Reasoning</span>
                                  <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{doc.reasoning}</p>
                                </div>
                              )}

                              {/* Flag / Human Review panel — visible to all */}
                              {doc.flag && (
                                <div className={`mt-3 p-3 rounded-lg border ${
                                  doc.flag.status === 'PENDING'
                                    ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-300 dark:border-amber-700'
                                    : 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-300 dark:border-emerald-700'
                                }`}>
                                  <div className="flex items-center gap-2 mb-2">
                                    <Flag className={`w-4 h-4 flex-shrink-0 ${doc.flag.status === 'PENDING' ? 'text-amber-600' : 'text-emerald-600'}`} />
                                    <span className={`text-xs font-semibold uppercase tracking-wide ${
                                      doc.flag.status === 'PENDING' ? 'text-amber-700 dark:text-amber-400' : 'text-emerald-700 dark:text-emerald-400'
                                    }`}>
                                      {doc.flag.status === 'PENDING' ? 'Flagged for DPO Review' : 'Human Review Complete'}
                                    </span>
                                  </div>

                                  {/* Employee flag details */}
                                  <p className="text-xs text-gray-600 dark:text-gray-400">
                                    <strong>{doc.flag.flagged_by_name}</strong> flagged this on{' '}
                                    {new Date(doc.flag.flagged_at).toLocaleString()}
                                  </p>
                                  <p className="text-sm text-gray-800 dark:text-gray-200 mt-1 italic">"{doc.flag.comment}"</p>
                                  {doc.flag.suggested_classification && (
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                      Suggested classification: <strong>{doc.flag.suggested_classification}</strong>
                                    </p>
                                  )}

                                  {/* CISO resolution */}
                                  {doc.flag.status === 'RESOLVED' && (
                                    <div className="mt-2 pt-2 border-t border-emerald-200 dark:border-emerald-800">
                                      <p className="text-xs text-gray-600 dark:text-gray-400">
                                        <strong>{doc.flag.resolved_by_name}</strong>{' '}
                                        {doc.flag.resolution_action === 'OVERRIDE'
                                          ? <>overrode classification to <strong>{doc.flag.override_classification}</strong></>
                                          : 'maintained the AI classification'
                                        }{' — '}
                                        {new Date(doc.flag.resolved_at!).toLocaleString()}
                                      </p>
                                      <p className="text-sm text-gray-800 dark:text-gray-200 mt-1 italic">"{doc.flag.resolution_comment}"</p>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="bg-gray-50 dark:bg-gray-700/50 px-6 py-4 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Showing {startIndex + 1}–{Math.min(startIndex + itemsPerPage, filteredDocuments.length)} of {filteredDocuments.length} results
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => setCurrentPage(Math.max(1, currentPage - 1))} disabled={currentPage === 1}
                    className="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors">
                    <ChevronLeft className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  </button>
                  {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((page) => (
                    <button key={page} onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1 rounded-lg transition-colors ${
                        currentPage === page ? 'bg-[#1E3A8A] text-white' : 'border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-400'
                      }`}>
                      {page}
                    </button>
                  ))}
                  <button onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))} disabled={currentPage === totalPages || totalPages === 0}
                    className="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors">
                    <ChevronRight className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Document Viewer Modal */}
      {selectedDocument && (
        <DocumentViewer docId={selectedDocument} onClose={() => setSelectedDocument(null)} />
      )}

      {/* ── DPO Flagged Documents Panel ── */}
      <Dialog open={showFlaggedPanel} onOpenChange={(open) => { setShowFlaggedPanel(open); }}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Flag className="w-5 h-5 text-amber-500" />
              Flagged Documents
            </DialogTitle>
            <DialogDescription>
              Review documents flagged by employees as potentially misclassified.
            </DialogDescription>
          </DialogHeader>

          {/* Filter tabs */}
          <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
            {(['PENDING', 'RESOLVED'] as const).map(status => (
              <button
                key={status}
                onClick={() => { setFlaggedFilter(status); loadFlaggedDocs(status); }}
                className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
                  flaggedFilter === status
                    ? status === 'PENDING'
                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                      : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                {status === 'PENDING' ? 'Pending Review' : 'Resolved'}
                {status === 'PENDING' && (
                  <span className="ml-1.5 px-1.5 py-0.5 bg-amber-500 text-white text-xs rounded-full">
                    {documents.filter(d => d.flag?.status === 'PENDING').length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Flagged docs list */}
          <div className="flex-1 overflow-y-auto space-y-3 py-2 min-h-0">
            {flaggedLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
              </div>
            ) : flaggedDocs.length === 0 ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                No {flaggedFilter.toLowerCase()} flags found.
              </div>
            ) : flaggedDocs.map(fd => (
              <div key={fd.doc_id} className={`p-4 rounded-lg border ${
                fd.flag.status === 'PENDING'
                  ? 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800'
                  : 'bg-gray-50 dark:bg-gray-700/30 border-gray-200 dark:border-gray-700'
              }`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                        {fd.original_filename || fd.doc_id}
                      </span>
                      <Badge className={`text-xs ${
                        fd.classification === 'C3' ? 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300' :
                        fd.classification === 'C2' ? 'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/30 dark:text-orange-300' :
                        fd.classification === 'C1' ? 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300' :
                                                     'bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300'
                      }`}>
                        {fd.classification}
                      </Badge>
                      {fd.department && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">{fd.department}</span>
                      )}
                    </div>

                    {/* Employee flag */}
                    <div className="mt-2">
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Flagged by <strong>{fd.flag.flagged_by_name}</strong> · {new Date(fd.flag.flagged_at).toLocaleString()}
                        {fd.flag.suggested_classification && (
                          <> · Suggested: <strong>{fd.flag.suggested_classification}</strong></>
                        )}
                      </p>
                      <p className="mt-1 text-sm text-gray-800 dark:text-gray-200 italic">"{fd.flag.comment}"</p>
                    </div>

                    {/* Resolution info (if resolved) */}
                    {fd.flag.status === 'RESOLVED' && (
                      <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          <strong>{fd.flag.resolved_by_name}</strong>{' '}
                          {fd.flag.resolution_action === 'OVERRIDE'
                            ? <>overrode to <strong>{fd.flag.override_classification}</strong></>
                            : 'maintained the classification'
                          }
                          {' · '}{new Date(fd.flag.resolved_at!).toLocaleString()}
                        </p>
                        <p className="mt-0.5 text-sm text-gray-700 dark:text-gray-300 italic">"{fd.flag.resolution_comment}"</p>
                      </div>
                    )}
                  </div>

                  {/* DPO resolve button — only for pending */}
                  {fd.flag.status === 'PENDING' && (
                    <Button
                      size="sm"
                      onClick={() => { openResolveDialog(fd.doc_id); }}
                      className="flex-shrink-0 bg-indigo-600 hover:bg-indigo-700 text-white"
                    >
                      <CheckCheck className="w-3.5 h-3.5 mr-1.5" />
                      Review
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* ── CISO Direct Override Dialog ── */}
      <Dialog open={!!editDocId} onOpenChange={(open) => !open && setEditDocId(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="w-5 h-5 text-violet-600" />
              Override Classification
            </DialogTitle>
            <DialogDescription>
              {editDocId && (() => {
                const d = documents.find(doc => doc.id === editDocId);
                return d ? <>Change classification for <strong>{d.name}</strong> (currently <strong>{d.classification}</strong>).</> : null;
              })()}
              {' '}Your reasoning will be stored to improve future AI classifications.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                New classification <span className="text-red-500">*</span>
              </label>
              <Select value={editNewClass} onValueChange={setEditNewClass}>
                <SelectTrigger>
                  <SelectValue placeholder="Select classification" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="C0">C0 — Public</SelectItem>
                  <SelectItem value="C1">C1 — Internal</SelectItem>
                  <SelectItem value="C2">C2 — Confidential</SelectItem>
                  <SelectItem value="C3">C3 — Strictly Confidential</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                Reasoning <span className="text-red-500">*</span>
                <span className="ml-1.5 text-xs text-gray-400 font-normal">— stored for LLM improvement</span>
              </label>
              <Textarea
                placeholder="Explain why the classification should change. This helps train the AI to make better decisions in future documents of this type."
                value={editReasoning}
                onChange={(e) => setEditReasoning(e.target.value)}
                className="min-h-28 resize-none"
              />
            </div>

            {editNewClass && editNewClass !== (documents.find(d => d.id === editDocId)?.classification) && (
              <div className="flex items-start gap-2 p-2.5 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-lg">
                <AlertTriangle className="w-4 h-4 text-violet-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-violet-700 dark:text-violet-300">
                  This will immediately change the document's classification from{' '}
                  <strong>{documents.find(d => d.id === editDocId)?.classification}</strong> to <strong>{editNewClass}</strong>.
                  The change and your reasoning will be logged permanently.
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDocId(null)} disabled={editSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={handleEditSubmit}
              disabled={editSubmitting || !editNewClass || !editReasoning.trim()}
              className="bg-violet-600 hover:bg-violet-700 text-white"
            >
              {editSubmitting
                ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                : <Pencil className="w-4 h-4 mr-1.5" />}
              Confirm Override
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Flag Dialog ── */}
      <Dialog open={!!flagDocId} onOpenChange={(open) => !open && setFlagDocId(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Flag className="w-5 h-5 text-amber-500" />
              Flag Document for Review
            </DialogTitle>
            <DialogDescription>
              Describe why you think this document is misclassified. The Data Protection Officer (DPO) will review your flag and can override the classification.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                Your comment <span className="text-red-500">*</span>
              </label>
              <Textarea
                placeholder="e.g., This document contains a customer account number and should be classified C3, not C2."
                value={flagComment}
                onChange={(e) => setFlagComment(e.target.value)}
                className="min-h-24 resize-none"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                Suggested correct classification <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <Select value={flagSuggested} onValueChange={setFlagSuggested}>
                <SelectTrigger>
                  <SelectValue placeholder="No suggestion — let DPO decide" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No suggestion</SelectItem>
                  <SelectItem value="C0">C0 — Public</SelectItem>
                  <SelectItem value="C1">C1 — Internal</SelectItem>
                  <SelectItem value="C2">C2 — Confidential</SelectItem>
                  <SelectItem value="C3">C3 — Strictly Confidential</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setFlagDocId(null)} disabled={flagSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={handleFlagSubmit}
              disabled={flagSubmitting || !flagComment.trim()}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {flagSubmitting
                ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                : <Flag className="w-4 h-4 mr-1.5" />}
              Submit Flag
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── DPO Resolve Dialog ── */}
      <Dialog open={!!resolveDocId} onOpenChange={(open) => !open && setResolveDocId(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCheck className="w-5 h-5 text-indigo-600" />
              Review Flagged Document
            </DialogTitle>
            <DialogDescription>
              Review the employee's flag and decide whether to maintain the AI classification or override it.
            </DialogDescription>
          </DialogHeader>

          {/* Show the employee's flag context */}
          {resolveDocId && (() => {
            const flaggedDoc = documents.find(d => d.id === resolveDocId);
            return flaggedDoc?.flag ? (
              <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-sm">
                <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-1">
                  Employee comment from {flaggedDoc.flag.flagged_by_name}
                </p>
                <p className="text-gray-800 dark:text-gray-200 italic">"{flaggedDoc.flag.comment}"</p>
                {flaggedDoc.flag.suggested_classification && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Suggested: <strong>{flaggedDoc.flag.suggested_classification}</strong>
                  </p>
                )}
              </div>
            ) : null;
          })()}

          <div className="space-y-4 py-1">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                Decision <span className="text-red-500">*</span>
              </label>
              <Select value={resolveAction} onValueChange={(v) => setResolveAction(v as 'MAINTAIN' | 'OVERRIDE')}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="MAINTAIN">MAINTAIN — Agree with AI classification</SelectItem>
                  <SelectItem value="OVERRIDE">OVERRIDE — Change to a different classification</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {resolveAction === 'OVERRIDE' && (
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                  New classification <span className="text-red-500">*</span>
                </label>
                <Select value={resolveOverride} onValueChange={setResolveOverride}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select classification" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="C0">C0 — Public</SelectItem>
                    <SelectItem value="C1">C1 — Internal</SelectItem>
                    <SelectItem value="C2">C2 — Confidential</SelectItem>
                    <SelectItem value="C3">C3 — Strictly Confidential</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1.5">
                Your comment <span className="text-red-500">*</span>
              </label>
              <Textarea
                placeholder={resolveAction === 'MAINTAIN'
                  ? "e.g., The AI classification is correct — the document contains no PII that would change its level."
                  : "e.g., After review, the document contains a full IBAN number which requires C3 classification per PDPL Art. 21."}
                value={resolveComment}
                onChange={(e) => setResolveComment(e.target.value)}
                className="min-h-24 resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setResolveDocId(null)} disabled={resolveSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={handleResolveSubmit}
              disabled={resolveSubmitting || !resolveComment.trim()}
              variant={resolveAction === 'OVERRIDE' ? 'destructive' : 'default'}
            >
              {resolveSubmitting
                ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                : resolveAction === 'OVERRIDE'
                  ? <RotateCcw className="w-4 h-4 mr-1.5" />
                  : <CheckCheck className="w-4 h-4 mr-1.5" />}
              {resolveAction === 'MAINTAIN' ? 'Confirm — Maintain Classification' : 'Confirm — Override Classification'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
