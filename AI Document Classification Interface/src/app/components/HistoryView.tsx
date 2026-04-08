import { useState, useEffect, useMemo, Fragment } from 'react';
import { Search, Download, Eye, Flag, CheckCircle, XCircle, ChevronLeft, ChevronRight, ChevronDown, RefreshCw, AlertCircle, Lock, Loader2, Shield, Brain, ScrollText } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip';
import { SecurityBadge } from './SecurityBadge';
import { DocumentViewer } from './DocumentViewer';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { getDocuments, getAuditLogs, downloadDocument, downloadTextWatermarked, type StoredDocument, type AuditLog } from '../services/api';

// Access level required for each classification
const classificationAccessLevel: Record<string, number> = {
  'C0': 1,  // Public - Level 1+
  'C1': 2,  // Internal - Level 2+ (Employee)
  'C2': 3,  // Confidential - Level 3+
  'C3': 4,  // Highly Sensitive - Level 4+
};

// Check if user can access (view) a document
const canAccessDocument = (userLevel: number, classification: string): boolean => {
  const requiredLevel = classificationAccessLevel[classification] || 1;
  return userLevel >= requiredLevel;
};

// Download permissions per policy matrix
// C0: L1+, C1: L2+, C2: L4+ (L3 = view only), C3: L5 (L4 = view only)
const canDownloadDocument = (userLevel: number, classification: string): boolean => {
  switch (classification) {
    case 'C0': return userLevel >= 1;
    case 'C1': return userLevel >= 2;
    case 'C2': return userLevel >= 4;
    case 'C3': return userLevel >= 5;
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
  rawTimestamp: number;  // For sorting
  encrypted: boolean;
  reasoning: string;
  triggers: string[];
}

export function HistoryView() {
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

  const userLevel = user?.access_level || 1;
  const isLevel5 = userLevel >= 5;

  const toggleRow = (docId: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const handleDownload = async (docId: string) => {
    setDownloadingDoc(docId);
    try {
      await downloadDocument(docId, user?.user_id);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Failed to download document. Please try again.');
    } finally {
      setDownloadingDoc(null);
    }
  };

  const handleDownloadWatermarked = async (docId: string) => {
    setDownloadingWatermark(docId);
    try {
      await downloadTextWatermarked(docId, user?.user_id);
    } catch (err) {
      console.error('Watermark download failed:', err);
      alert('Failed to download watermarked document. Please try again.');
    } finally {
      setDownloadingWatermark(null);
    }
  };

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const [storedDocs, auditData] = await Promise.all([
        getDocuments(),
        getAuditLogs(),
      ]);

      // Create a map of audit logs by document ID for additional info
      const auditMap = new Map<string, AuditLog>();
      auditData.logs.forEach(log => {
        if (log.event_type === 'DOCUMENT_CLASSIFIED') {
          const docId = (log.data as { document_id?: string }).document_id;
          if (docId) {
            auditMap.set(docId, log);
          }
        }
      });

      // Transform stored documents to our format (skip any without doc_id)
      const docs: Document[] = storedDocs
        .filter((doc) => doc?.doc_id)
        .map((doc) => {
          const auditLog = auditMap.get(doc.doc_id);
          const method = doc.method || (auditLog?.data as { method?: string })?.method || 'AGREEMENT';

          const docDate = new Date(doc.timestamp);
          return {
            id: doc.doc_id,
            name: doc.doc_id,
            classification: doc.classification,
            confidence: doc.confidence != null ? doc.confidence : 0.95,
            method: method,
            llmResult: doc.llm_classification || doc.classification,
            rulesResult: doc.rules_classification || 'None',
            agreement: method === 'AGREEMENT',
            timestamp: docDate.toLocaleString(),
            rawTimestamp: docDate.getTime(),
            encrypted: doc.encrypted,
            reasoning: doc.reasoning || '',
            triggers: doc.triggers || [],
          };
        });

      setDocuments(docs);
    } catch (err) {
      setError('Failed to load documents. Is the API server running?');
      console.error('Error fetching documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  // Filter documents based on user access level AND search/filters
  const accessibleDocuments = documents.filter(doc => canAccessDocument(userLevel, doc.classification));

  // Classification level mapping for sorting
  const classificationOrder: Record<string, number> = { 'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3 };

  const filteredDocuments = useMemo(() => {
    // First filter
    const filtered = accessibleDocuments.filter((doc) => {
      const matchesSearch = doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           doc.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesLevel = filterLevel === 'all' || doc.classification === filterLevel;
      const matchesEncrypted = filterEncrypted === 'all' ||
                              (filterEncrypted === 'yes' && doc.encrypted) ||
                              (filterEncrypted === 'no' && !doc.encrypted);

      return matchesSearch && matchesLevel && matchesEncrypted;
    });

    // Then sort
    return [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'date-desc':
          return b.rawTimestamp - a.rawTimestamp;
        case 'date-asc':
          return a.rawTimestamp - b.rawTimestamp;
        case 'class-desc':
          return classificationOrder[b.classification] - classificationOrder[a.classification];
        case 'class-asc':
          return classificationOrder[a.classification] - classificationOrder[b.classification];
        case 'name-asc':
          return a.name.localeCompare(b.name);
        case 'name-desc':
          return b.name.localeCompare(a.name);
        default:
          return 0;
      }
    });
  }, [accessibleDocuments, searchTerm, filterLevel, filterEncrypted, sortBy]);

  // Count restricted documents
  const restrictedCount = documents.length - accessibleDocuments.length;

  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedDocuments = filteredDocuments.slice(startIndex, startIndex + itemsPerPage);

  const exportToCsv = () => {
    const headers = isLevel5
      ? ['ID', 'Classification', 'Method', 'LLM Result', 'Rules Result', 'Confidence', 'Triggers', 'Reasoning', 'Encrypted', 'Timestamp']
      : ['ID', 'Classification', 'Method', 'Encrypted', 'Timestamp'];

    const rows = filteredDocuments.map(doc => {
      if (isLevel5) {
        return [
          doc.id,
          doc.classification,
          doc.method,
          doc.llmResult,
          doc.rulesResult,
          typeof doc.confidence === 'number' ? `${(doc.confidence * 100).toFixed(0)}%` : 'N/A',
          doc.triggers.join('; '),
          `"${(doc.reasoning || '').replace(/"/g, '""')}"`,
          doc.encrypted ? 'Yes' : 'No',
          doc.timestamp,
        ];
      }
      return [
        doc.id,
        doc.classification,
        doc.method,
        doc.encrypted ? 'Yes' : 'No',
        doc.timestamp,
      ];
    });

    const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n');
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
          <button
            onClick={fetchDocuments}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-6 ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('history.title')}</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t('history.showing')} {accessibleDocuments.length} {t('history.documents')}
          </p>
        </div>
        <div className="flex items-center gap-3">
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
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
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

          {/* Classification Level Filter */}
          <div className="w-full lg:w-48">
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
            >
              <option value="all">{t('history.allLevels')}</option>
              <option value="C0">C0 - {t('common.public')}</option>
              <option value="C1">C1 - {t('common.internal')}</option>
              <option value="C2">C2 - {t('common.confidential')}</option>
              <option value="C3">C3 - {t('common.highlySensitive')}</option>
            </select>
          </div>

          {/* Encrypted Filter */}
          <div className="w-full lg:w-48">
            <select
              value={filterEncrypted}
              onChange={(e) => setFilterEncrypted(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
            >
              <option value="all">{t('history.allDocuments')}</option>
              <option value="yes">{t('history.encryptedOnly')}</option>
              <option value="no">{t('history.notEncrypted')}</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="w-full lg:w-52">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
            >
              <option value="date-desc">{t('history.sortDateNewest') || 'Date (Newest First)'}</option>
              <option value="date-asc">{t('history.sortDateOldest') || 'Date (Oldest First)'}</option>
              <option value="class-desc">{t('history.sortClassHigh') || 'Classification (C3→C0)'}</option>
              <option value="class-asc">{t('history.sortClassLow') || 'Classification (C0→C3)'}</option>
              <option value="name-asc">{t('history.sortNameAZ') || 'Name (A→Z)'}</option>
              <option value="name-desc">{t('history.sortNameZA') || 'Name (Z→A)'}</option>
            </select>
          </div>

          {/* Export Button */}
          <button
            onClick={exportToCsv}
            disabled={filteredDocuments.length === 0}
            className="px-4 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-all flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
          >
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
              {documents.length === 0
                ? t('history.noDocuments')
                : t('history.noMatches')}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
                  <tr>
                    <th className={`px-6 py-3 ${isRTL ? 'text-right' : 'text-left'} text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider`}>
                      {t('history.document')}
                    </th>
                    <th className={`px-6 py-3 ${isRTL ? 'text-right' : 'text-left'} text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider`}>
                      {t('history.classification')}
                    </th>
                    <th className={`px-6 py-3 ${isRTL ? 'text-right' : 'text-left'} text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider`}>
                      {t('history.method')}
                    </th>
                    <th className={`px-6 py-3 ${isRTL ? 'text-right' : 'text-left'} text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider`}>
                      {t('history.encrypted')}
                    </th>
                    <th className={`px-6 py-3 ${isRTL ? 'text-right' : 'text-left'} text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider`}>
                      {t('history.timestamp')}
                    </th>
                    <th className={`px-6 py-3 ${isRTL ? 'text-right' : 'text-left'} text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider`}>
                      {t('history.actions')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {paginatedDocuments.map((doc) => (
                    <Fragment key={doc.id}>
                      <tr className={`hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${isLevel5 ? 'cursor-pointer' : ''}`}
                          onClick={isLevel5 ? () => toggleRow(doc.id) : undefined}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {isLevel5 && (
                              <span className="text-gray-400">
                                {expandedRows.has(doc.id) ? (
                                  <ChevronDown className="w-4 h-4" />
                                ) : (
                                  <ChevronRight className="w-4 h-4" />
                                )}
                              </span>
                            )}
                            <div>
                              <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                {doc.name}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">{doc.id}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <SecurityBadge level={doc.classification} size="sm" />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            doc.method === 'AGREEMENT'
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                              : doc.method === 'RULES_OVERRIDE'
                              ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400'
                              : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                          }`}>
                            {doc.method.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {doc.encrypted ? (
                            <CheckCircle className="w-5 h-5 text-[#10B981]" />
                          ) : (
                            <XCircle className="w-5 h-5 text-gray-400" />
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900 dark:text-gray-100">{doc.timestamp}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  onClick={() => setSelectedDocument(doc.id)}
                                  className="p-1 hover:bg-gray-100 dark:hover:bg-gray-600 rounded transition-colors"
                                >
                                  <Eye className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">View document details</TooltipContent>
                            </Tooltip>

                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  onClick={() => canDownloadDocument(userLevel, doc.classification) && handleDownload(doc.id)}
                                  disabled={downloadingDoc === doc.id || !canDownloadDocument(userLevel, doc.classification)}
                                  className={`p-1 rounded transition-colors ${canDownloadDocument(userLevel, doc.classification) ? 'hover:bg-blue-100 dark:hover:bg-blue-900/30' : 'opacity-30 cursor-not-allowed'}`}
                                >
                                  {downloadingDoc === doc.id ? (
                                    <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />
                                  ) : (
                                    <ScrollText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                  )}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                {canDownloadDocument(userLevel, doc.classification) ? 'Download OCR extracted text (.txt)' : 'Download not permitted for your access level'}
                              </TooltipContent>
                            </Tooltip>

                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  onClick={() => canDownloadDocument(userLevel, doc.classification) && handleDownloadWatermarked(doc.id)}
                                  disabled={downloadingWatermark === doc.id || !canDownloadDocument(userLevel, doc.classification)}
                                  className={`p-1 rounded transition-colors ${canDownloadDocument(userLevel, doc.classification) ? 'hover:bg-indigo-100 dark:hover:bg-indigo-900/30' : 'opacity-30 cursor-not-allowed'}`}
                                >
                                  {downloadingWatermark === doc.id ? (
                                    <Loader2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400 animate-spin" />
                                  ) : (
                                    <Download className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                                  )}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                {canDownloadDocument(userLevel, doc.classification) ? 'Download with classification watermark (.pdf)' : 'Download not permitted for your access level'}
                              </TooltipContent>
                            </Tooltip>

                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button className="p-1 hover:bg-gray-100 dark:hover:bg-gray-600 rounded transition-colors">
                                  <Flag className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="top">Flag for review</TooltipContent>
                            </Tooltip>
                          </div>
                        </td>
                      </tr>

                      {/* Expanded Detail Row - Level 5 Only */}
                      {isLevel5 && expandedRows.has(doc.id) && (
                        <tr>
                          <td colSpan={6} className="px-6 py-0">
                            <div className="py-4 pl-6 border-l-4 border-indigo-400 dark:border-indigo-600 ml-2 mb-2">
                              <div className="flex items-center gap-2 mb-3">
                                <Shield className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                                <span className="text-sm font-semibold text-indigo-800 dark:text-indigo-300">Classification Analysis</span>
                                <span className="text-xs px-1.5 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded">Admin</span>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
                                {/* LLM vs Rules */}
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
                                    {typeof doc.confidence === 'number' ? `${(doc.confidence * 100).toFixed(0)}%` : 'N/A'}
                                  </span>
                                </div>
                              </div>

                              {/* Triggers */}
                              {doc.triggers && doc.triggers.length > 0 && (
                                <div className="mb-3">
                                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400 mr-2">Triggers:</span>
                                  {doc.triggers.map((trigger, idx) => (
                                    <span key={idx} className="inline-block text-xs px-2 py-0.5 mr-1 mb-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
                                      {trigger}
                                    </span>
                                  ))}
                                </div>
                              )}

                              {/* Reasoning */}
                              {doc.reasoning && (
                                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400 block mb-1">AI Reasoning</span>
                                  <p className="text-sm text-gray-700 dark:text-gray-300">{doc.reasoning}</p>
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
                  Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, filteredDocuments.length)} of {filteredDocuments.length} results
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  </button>
                  {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((page) => (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1 rounded-lg transition-colors ${
                        currentPage === page
                          ? 'bg-[#1E3A8A] text-white'
                          : 'border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-400'
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                  <button
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages || totalPages === 0}
                    className="p-2 rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
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
        <DocumentViewer
          docId={selectedDocument}
          onClose={() => setSelectedDocument(null)}
        />
      )}
    </div>
  );
}
