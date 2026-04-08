import { useState, useEffect } from 'react';
import { Upload, X, File, CheckCircle, AlertCircle, Cloud, Settings as SettingsIcon, Loader2, Shield, Lock, Ban, RefreshCw, Database, FileText, Cpu, Scale, ClipboardList, CheckCircle2, ChevronDown, ChevronRight, Download } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from './ui/tooltip';
import { classifyDocumentWithSteps, classifyPDFWithSteps, getUsers, getSampleDocuments, generateDataset, getDatasetInfo, downloadDocument, downloadWatermarkedFile, type ClassificationResult, type PipelineStepsResult, type User, type DatasetInfo } from '../services/api';
import { SecurityBadge } from './SecurityBadge';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  content: string;
  progress: number;
  status: 'uploading' | 'classifying' | 'completed' | 'error';
  result?: ClassificationResult;
  pipelineResult?: PipelineStepsResult;
  error?: string;
  originalFile?: File;  // Keep original file for PDF handling
  isPDF?: boolean;
  classifyStartedAt?: number;  // Date.now() when classifying began
  ocrTotalSeconds?: number;    // Client-measured total time on completion
}

function stepsToClassificationResult(data: PipelineStepsResult): ClassificationResult {
  const s = data.pipeline_result.stages;
  return {
    success: data.success,
    doc_id: data.doc_id,
    classification: s.classification.classification,
    confidence: s.classification.confidence,
    confidence_factors: s.classification.confidence_factors,
    confidence_explanation: s.classification.confidence_explanation,
    llm_raw_confidence: s.classification.llm_raw_confidence ?? undefined,
    method: s.classification.method,
    llm_classification: s.classification.llm_classification,
    rules_classification: s.classification.rules_classification ?? '',
    agreement: s.classification.agreement,
    reasoning: s.classification.reasoning,
    triggers: s.classification.triggers,
    encrypted: s.encryption.encrypted,
    storage_path: s.storage.path ?? s.storage.storage_path ?? '',
    timestamp: data.pipeline_result.timestamp,
    access: s.access,
  };
}

export function UploadView() {
  const { user } = useAuth();
  const { settings, t, isRTL } = useSettings();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [isClassifying, setIsClassifying] = useState(false);
  const [textInput, setTextInput] = useState('');
  const [inputMode, setInputMode] = useState<'file' | 'text'>('file');
  const [isGenerating, setIsGenerating] = useState(false);
  const [datasetInfo, setDatasetInfo] = useState<DatasetInfo | null>(null);
  const [generateCount, setGenerateCount] = useState(100);
  const [trueLabel, setTrueLabel] = useState<string>(''); // Ground truth for evaluation
  const [, setClockTick] = useState(0); // Increments every second to drive live timer re-renders
  const [expandedSteps, setExpandedSteps] = useState<Record<string, number[]>>({});

  const toggleStep = (fileId: string, stepIndex: number) => {
    setExpandedSteps(prev => {
      const current = prev[fileId] ?? [];
      const next = current.includes(stepIndex)
        ? current.filter(i => i !== stepIndex)
        : [...current, stepIndex];
      return { ...prev, [fileId]: next };
    });
  };

  const [downloadingText, setDownloadingText] = useState<Record<string, boolean>>({});
  const [downloadingWatermark, setDownloadingWatermark] = useState<Record<string, boolean>>({});

  const handleDownloadText = async (file: UploadedFile) => {
    if (!file.result?.doc_id) return;
    setDownloadingText(prev => ({ ...prev, [file.id]: true }));
    try {
      await downloadDocument(file.result.doc_id, selectedUser || undefined);
    } catch (err) {
      console.error('OCR text download failed:', err);
    } finally {
      setDownloadingText(prev => ({ ...prev, [file.id]: false }));
    }
  };

  const handleDownloadWatermarked = async (file: UploadedFile) => {
    if (!file.result?.doc_id || !file.originalFile) return;
    setDownloadingWatermark(prev => ({ ...prev, [file.id]: true }));
    try {
      await downloadWatermarkedFile(file.result.doc_id, file.originalFile);
    } catch (err) {
      console.error('Watermark download failed:', err);
    } finally {
      setDownloadingWatermark(prev => ({ ...prev, [file.id]: false }));
    }
  };

  // Keep a live clock while any file is being classified
  useEffect(() => {
    const isClassifying = files.some(f => f.status === 'classifying');
    if (!isClassifying) return;
    const id = setInterval(() => setClockTick(t => t + 1), 100);
    return () => clearInterval(id);
  }, [files.some(f => f.status === 'classifying')]); // eslint-disable-line react-hooks/exhaustive-deps

  const userLevel = user?.access_level || 1;
  const canUpload = userLevel >= 2; // Employee (Level 2) or higher can upload

  // Build classification settings from context
  const classificationSettings = {
    confidenceThreshold: settings.confidenceThreshold,
    hybridMode: settings.hybridMode,
    autoEscalate: settings.autoEscalate,
    autoEncryptC2C3: settings.autoEncryptC2C3,
  };

  const loadUsers = async () => {
    try {
      const usersData = await getUsers();
      setUsers(usersData);
    } catch (err) {
      console.error('Failed to load users:', err);
    }
  };

  const loadDatasetInfo = async () => {
    try {
      const info = await getDatasetInfo();
      setDatasetInfo(info);
    } catch (err) {
      console.error('Failed to load dataset info:', err);
    }
  };

  const handleGenerateDataset = async () => {
    setIsGenerating(true);
    try {
      const result = await generateDataset(generateCount);
      alert(`✅ Generated ${result.count} documents!\n\nDistribution:\n- C0: ${result.distribution.C0 || 0}\n- C1: ${result.distribution.C1 || 0}\n- C2: ${result.distribution.C2 || 0}\n- C3: ${result.distribution.C3 || 0}\n\nFeatures:\n${result.features.map(f => '• ' + f).join('\n')}`);
      loadDatasetInfo();
    } catch (err) {
      alert('❌ Failed to generate dataset: ' + (err instanceof Error ? err.message : 'Unknown error'));
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    loadUsers();
    loadDatasetInfo();
  }, []);

  // Access Denied for Level 1 (Public) users
  if (!canUpload) {
    return (
      <div className={`p-6 max-w-2xl mx-auto ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto mb-4">
            <Ban className="w-8 h-8 text-red-600 dark:text-red-400" />
          </div>
          <h2 className="text-xl font-semibold text-red-800 dark:text-red-300 mb-2">
            {t('upload.accessRestricted')}
          </h2>
          <p className="text-red-600 dark:text-red-400 mb-4">
            {t('upload.accessRestrictedMsg')}
          </p>
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-red-200 dark:border-red-800">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{t('upload.yourAccess')}</p>
            <div className="flex items-center justify-center gap-2">
              <Lock className="w-4 h-4 text-gray-500" />
              <span className="font-medium text-gray-900 dark:text-gray-100">
                Level {userLevel} - {user?.role || 'Public'}
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              {t('upload.canViewC0')}
            </p>
          </div>
          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
            <p className="text-sm text-blue-700 dark:text-blue-400">
              <strong>Access Levels:</strong>
            </p>
            <ul className="text-xs text-blue-600 dark:text-blue-400 mt-2 space-y-1">
              <li>Level 1 (Public): View C0 only</li>
              <li>Level 2 (Employee): View C0-C1, Upload documents</li>
              <li>Level 3 (Manager): View C0-C2, Upload documents</li>
              <li>Level 4+ (Admin): Full access</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  const loadSampleDocument = async () => {
    try {
      const samples = await getSampleDocuments(1);
      if (samples.length > 0) {
        setTextInput(samples[0].text);
        setInputMode('text');
      }
    } catch (err) {
      console.error('Failed to load sample:', err);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      addFiles(selectedFiles);
    }
  };

  const addFiles = async (newFiles: File[]) => {
    for (const file of newFiles) {
      const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const isPdfOrImage = /\.(pdf|png|jpe?g|gif|webp|bmp|tiff?)$/i.test(file.name);

      // For PDF/image, don't read as text - let the server handle extraction (and OCR)
      const content = isPdfOrImage ? '[Document - will be extracted server-side]' : await readFileContent(file);

      const uploadedFile: UploadedFile = {
        id,
        name: file.name,
        size: file.size,
        content,
        progress: 100,
        status: 'uploading',
        originalFile: isPdfOrImage ? file : undefined,
        isPDF: isPdfOrImage,
      };

      setFiles(prev => [...prev, uploadedFile]);

      // Mark as ready for classification
      setTimeout(() => {
        setFiles(prev => prev.map(f =>
          f.id === id ? { ...f, status: 'uploading' } : f
        ));
      }, 500);
    }
  };

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        resolve(content);
      };
      reader.onerror = reject;
      reader.readAsText(file);
    });
  };

  const removeFile = (fileId: string) => {
    setFiles(files.filter((f) => f.id !== fileId));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const classifyFiles = async () => {
    setIsClassifying(true);

    // Handle text input mode
    if (inputMode === 'text' && textInput.trim()) {
      const id = `TEXT-${Date.now()}`;
      const textFile: UploadedFile = {
        id,
        name: `text_input_${Date.now()}.txt`,
        size: textInput.length,
        content: textInput,
        progress: 0,
        status: 'classifying',
      };

      setFiles(prev => [...prev, textFile]);

      try {
        const data = await classifyDocumentWithSteps(
          textInput,
          `DOC_${Date.now()}`,
          selectedUser || user?.user_id || undefined,
          classificationSettings,
        );
        const result = stepsToClassificationResult(data);
        setFiles(prev => prev.map(f =>
          f.id === id ? { ...f, status: 'completed', progress: 100, result, pipelineResult: data } : f
        ));
        setExpandedSteps(prev => ({ ...prev, [id]: [0, 1, 2, 3, 4, 5, 6] }));
        setTextInput('');
      } catch (err) {
        setFiles(prev => prev.map(f =>
          f.id === id ? { ...f, status: 'error', error: 'Classification failed' } : f
        ));
      }
    }

    // Handle file mode
    for (const file of files.filter(f => f.status === 'uploading')) {
      setFiles(prev => prev.map(f =>
        f.id === file.id ? { ...f, status: 'classifying', progress: 50, classifyStartedAt: Date.now() } : f
      ));

      try {
        let data: PipelineStepsResult;

        if (file.isPDF && file.originalFile) {
          data = await classifyPDFWithSteps(
            file.originalFile,
            file.name.replace(/\.[^/.]+$/, ''),
            selectedUser || user?.user_id || undefined
          );
        } else {
          data = await classifyDocumentWithSteps(
            file.content,
            file.name.replace(/\.[^/.]+$/, ''),
            selectedUser || user?.user_id || undefined,
            classificationSettings,
          );
        }

        const result = stepsToClassificationResult(data);
        setFiles(prev => prev.map(f =>
          f.id === file.id ? {
            ...f, status: 'completed', progress: 100, result, pipelineResult: data,
            ocrTotalSeconds: f.classifyStartedAt
              ? (Date.now() - f.classifyStartedAt) / 1000
              : undefined,
          } : f
        ));
        setExpandedSteps(prev => ({ ...prev, [file.id]: [0, 1, 2, 3, 4, 5, 6] }));
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Classification failed';
        setFiles(prev => prev.map(f =>
          f.id === file.id ? { ...f, status: 'error', error: errorMsg } : f
        ));
      }
    }

    setIsClassifying(false);
  };

  const hasFilesToClassify = files.some(f => f.status === 'uploading') || (inputMode === 'text' && textInput.trim());

  return (
    <div className={`p-6 max-w-7xl mx-auto ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('upload.title')}</h2>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          {t('upload.subtitle')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Area */}
        <div className="lg:col-span-2 space-y-6">
          {/* Input Mode Toggle */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setInputMode('file')}
              className={`px-4 py-2 rounded-lg transition-all ${
                inputMode === 'file'
                  ? 'bg-[#1E3A8A] text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
              }`}
            >
              {t('upload.uploadFile')}
            </button>
            <button
              onClick={() => setInputMode('text')}
              className={`px-4 py-2 rounded-lg transition-all ${
                inputMode === 'text'
                  ? 'bg-[#1E3A8A] text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
              }`}
            >
              {t('upload.pasteText')}
            </button>
          </div>

          {inputMode === 'file' ? (
            /* Drag and Drop Zone */
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-12 text-center transition-all ${
                isDragging
                  ? 'border-[#0891B2] bg-cyan-50 dark:bg-cyan-900/20'
                  : 'border-gray-300 dark:border-gray-600 hover:border-[#0891B2] dark:hover:border-[#0891B2]'
              }`}
            >
              <div className="flex flex-col items-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#0891B2] flex items-center justify-center mb-4">
                  <Cloud className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                  {t('upload.dropHere')}
                </h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">
                  {t('upload.orBrowse')}
                </p>
                <input
                  type="file"
                  id="file-upload"
                  multiple
                  onChange={handleFileSelect}
                  className="hidden"
                  accept=".txt,.pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp,.bmp,.tiff,.tif"
                />
                <label
                  htmlFor="file-upload"
                  className="px-6 py-3 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-all cursor-pointer font-medium"
                >
                  {t('upload.browseFiles')}
                </label>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">
                  {t('upload.supportedFormats')}
                </p>
              </div>
            </div>
          ) : (
            /* Text Input Area */
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {t('upload.documentText')}
                </h3>
                <button
                  onClick={loadSampleDocument}
                  className="text-sm text-[#0891B2] hover:underline"
                >
                  {t('upload.loadSample')}
                </button>
              </div>
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder={t('upload.pasteContent')}
                className="w-full h-64 p-4 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 resize-none"
              />
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                {textInput.length} {t('upload.characters')}
              </p>
            </div>
          )}

          {/* Results Queue */}
          {files.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                {t('upload.classificationResults')} ({files.length})
              </h3>
              <div className="space-y-4">
                {files.map((file) => (
                  <div
                    key={file.id}
                    className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
                  >
                    <div className="flex items-center gap-4 mb-3">
                      <div className="w-10 h-10 rounded-lg bg-white dark:bg-gray-800 flex items-center justify-center flex-shrink-0">
                        <File className="w-5 h-5 text-[#1E3A8A]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {file.name}
                          </p>
                          <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                            {formatFileSize(file.size)}
                          </span>
                        </div>
                        {file.status === 'classifying' && (() => {
                          const elapsed = file.classifyStartedAt
                            ? (Date.now() - file.classifyStartedAt) / 1000
                            : 0;
                          // Smooth fill: reaches ~90% at 60s, holds until done
                          const pct = Math.min((elapsed / 60) * 90, 90);
                          return (
                            <div className="mt-1">
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                  <Loader2 className="w-4 h-4 text-[#0891B2] animate-spin flex-shrink-0" />
                                  <span className="text-sm text-[#0891B2]">{t('upload.classifying')}</span>
                                </div>
                                <span className="text-xs font-mono text-[#0891B2] tabular-nums">
                                  {elapsed.toFixed(1)}s
                                </span>
                              </div>
                              <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                                <div
                                  className="bg-gradient-to-r from-[#1E3A8A] to-[#0891B2] h-1.5 rounded-full transition-all duration-100"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                      <div className="flex items-center gap-2">
                        {file.status === 'completed' && (
                          <CheckCircle className="w-5 h-5 text-[#10B981]" />
                        )}
                        {file.status === 'error' && (
                          <AlertCircle className="w-5 h-5 text-[#EF4444]" />
                        )}
                        <button
                          onClick={() => removeFile(file.id)}
                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                        >
                          <X className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                        </button>
                      </div>
                    </div>

                    {/* Classification Result */}
                    {file.result && (
                      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div>
                            <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Classification</span>
                            <SecurityBadge level={file.result.classification} size="sm" />
                          </div>
                          <div>
                            <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Confidence</span>
                            <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
                              {(file.result.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div>
                            <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Method</span>
                            <span className="text-xs px-2 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
                              Hybrid AI
                            </span>
                          </div>
                          <div>
                            <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Encrypted</span>
                            <span className="flex items-center gap-1">
                              {file.result.encrypted ? (
                                <>
                                  <Lock className="w-4 h-4 text-[#10B981]" />
                                  <span className="text-sm text-[#10B981]">Yes</span>
                                </>
                              ) : (
                                <span className="text-sm text-gray-500">No</span>
                              )}
                            </span>
                          </div>
                        </div>

                        {/* OCR timing (images only) */}
                        {(file.result.ocr_job_seconds !== undefined || file.ocrTotalSeconds !== undefined) && (
                          <div className="mt-3 flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                            <span>⏱</span>
                            <span>
                              {file.result.ocr_job_seconds !== undefined
                                ? <>OCR + classification completed in <span className="font-semibold text-gray-700 dark:text-gray-300">{file.result.ocr_job_seconds}s</span> (server)</>
                                : <>Completed in <span className="font-semibold text-gray-700 dark:text-gray-300">{file.ocrTotalSeconds!.toFixed(1)}s</span></>
                              }
                            </span>
                          </div>
                        )}

                        {/* Confidence Breakdown - Multi-Factor Scoring */}
                        {file.result.confidence_factors && (
                          <div className="mt-4 p-4 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                            <div className="flex items-center gap-2 mb-3">
                              <span className="text-lg">📊</span>
                              <span className="font-medium text-purple-700 dark:text-purple-400">Multi-Factor Confidence Scoring</span>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                              {/* Agreement Factor */}
                              <div className="text-center">
                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Agreement (Dietterich, 2000)</div>
                                <div className="relative h-3 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                                  <div
                                    className="absolute left-0 top-0 h-full bg-green-500 rounded-full"
                                    style={{ width: `${file.result.confidence_factors.agreement * 100}%` }}
                                  />
                                </div>
                                <div className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-1">
                                  {(file.result.confidence_factors.agreement * 100).toFixed(0)}%
                                </div>
                              </div>
                              {/* Evidence Factor */}
                              <div className="text-center">
                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Evidence (Dempster-Shafer, 1967)</div>
                                <div className="relative h-3 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                                  <div
                                    className="absolute left-0 top-0 h-full bg-blue-500 rounded-full"
                                    style={{ width: `${file.result.confidence_factors.evidence * 100}%` }}
                                  />
                                </div>
                                <div className="text-sm font-semibold text-gray-700 dark:text-gray-300 mt-1">
                                  {(file.result.confidence_factors.evidence * 100).toFixed(0)}%
                                </div>
                              </div>
                            </div>
                            <div className="mt-3 text-xs text-gray-500 dark:text-gray-400 text-center">
                              Formula: 0.50 × Agreement + 0.50 × Evidence
                            </div>
                          </div>
                        )}

                        <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-400">
                              <span className="text-lg">🤖</span>
                              <span className="font-medium">Classified by Hybrid AI (LLaMA 3 + Security Rules)</span>
                            </div>
                            <div className="text-xs text-blue-600 dark:text-blue-400">
                              Method: {file.result.method}
                            </div>
                          </div>
                          {file.result.triggers && file.result.triggers.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {file.result.triggers.map((trigger, idx) => (
                                <span key={idx} className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-300 rounded-full">
                                  {trigger}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-600 rounded-lg">
                          <span className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Reasoning</span>
                          <p className="text-sm text-gray-700 dark:text-gray-300">{file.result.reasoning}</p>
                        </div>

                        {file.result.access && (
                          <div className={`mt-4 p-3 rounded-lg ${
                            file.result.access.granted
                              ? 'bg-green-100 dark:bg-green-900/20'
                              : 'bg-red-100 dark:bg-red-900/20'
                          }`}>
                            <span className="flex items-center gap-2">
                              <Shield className={`w-4 h-4 ${file.result.access.granted ? 'text-green-600' : 'text-red-600'}`} />
                              <span className={`text-sm font-medium ${file.result.access.granted ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                                Access {file.result.access.granted ? 'Granted' : 'Denied'}
                                {file.result.access.reason && `: ${file.result.access.reason}`}
                              </span>
                            </span>
                          </div>
                        )}

                        {/* Download buttons */}
                        {(() => {
                          const classification = file.result?.classification || 'C0';
                          const canDl = (() => {
                            switch (classification) {
                              case 'C0': return userLevel >= 1;
                              case 'C1': return userLevel >= 2;
                              case 'C2': return userLevel >= 4;
                              case 'C3': return userLevel >= 5;
                              default:   return false;
                            }
                          })();
                          return (
                            <div className="mt-4 flex flex-wrap gap-2">
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    onClick={() => canDl && handleDownloadText(file)}
                                    disabled={downloadingText[file.id] || !canDl}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${canDl ? 'bg-blue-50 hover:bg-blue-100 text-blue-700 dark:bg-blue-900/20 dark:hover:bg-blue-900/40 dark:text-blue-400 border-blue-200 dark:border-blue-800' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 border-gray-200 dark:border-gray-600 cursor-not-allowed opacity-60'}`}
                                  >
                                    {downloadingText[file.id]
                                      ? <Loader2 className="w-4 h-4 animate-spin" />
                                      : <FileText className="w-4 h-4" />}
                                    {canDl ? 'Download OCR Text' : 'Download Restricted'}
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom">
                                  {canDl ? 'Download the full OCR extracted text as a .txt file' : 'Download not permitted for your access level'}
                                </TooltipContent>
                              </Tooltip>

                              {file.originalFile && (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <button
                                      onClick={() => canDl && handleDownloadWatermarked(file)}
                                      disabled={downloadingWatermark[file.id] || !canDl}
                                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${canDl ? 'bg-indigo-50 hover:bg-indigo-100 text-indigo-700 dark:bg-indigo-900/20 dark:hover:bg-indigo-900/40 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800' : 'bg-gray-100 dark:bg-gray-700 text-gray-400 border-gray-200 dark:border-gray-600 cursor-not-allowed opacity-60'}`}
                                    >
                                      {downloadingWatermark[file.id]
                                        ? <Loader2 className="w-4 h-4 animate-spin" />
                                        : <Download className="w-4 h-4" />}
                                      {canDl ? 'Download with Watermark' : 'Download Restricted'}
                                    </button>
                                  </TooltipTrigger>
                                  <TooltipContent side="bottom">
                                    {canDl ? 'Download the original file with the classification watermark applied' : 'Download not permitted for your access level'}
                                  </TooltipContent>
                                </Tooltip>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    )}

                    {/* Pipeline Steps */}
                    {file.pipelineResult && (() => {
                      const stages = file.pipelineResult.pipeline_result.stages;
                      const extraction = file.pipelineResult.extraction;
                      const fileSteps = expandedSteps[file.id] ?? [];
                      const isOpen = (i: number) => fileSteps.includes(i);

                      let idx = 0;
                      type Step = { i: number; title: string; icon: React.ElementType; body: React.ReactNode };
                      const steps: Step[] = [];

                      if (extraction) {
                        const si = idx++;
                        steps.push({ i: si, title: extraction.source === 'image' ? '1. Image OCR Extraction' : '1. Document Text Extraction', icon: FileText, body: (
                          <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60 text-xs">
                            {([
                              ['Source', extraction.source ?? 'pdf'],
                              ['Method', extraction.method],
                              ['Pages', String(extraction.pages)],
                              ['Text length', `${extraction.text_length} chars`],
                              extraction.ocr_used != null ? ['OCR used', extraction.ocr_used ? 'Yes' : 'No'] : null,
                              extraction.language ? ['Language', extraction.language] : null,
                              extraction.notes ? ['Notes', extraction.notes] : null,
                            ] as ([string, string] | null)[]).filter(Boolean).map(([label, value], k) => (
                              <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                                <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                                <span className="text-gray-900 dark:text-gray-100 font-medium text-right break-all">{value}</span>
                              </div>
                            ))}
                          </div>
                        )});
                      }

                      const classNum = extraction ? '2' : '1';
                      const ci = idx++;
                      steps.push({ i: ci, title: `${classNum}. Hybrid Classification`, icon: Cpu, body: (
                        <div className="space-y-2 text-xs">
                          <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60">
                            {[
                              ['LLM result', stages.classification.llm_classification],
                              ['Rules result', stages.classification.rules_classification ?? 'No triggers'],
                              ['Method', stages.classification.method],
                              ['Agreement', stages.classification.agreement ? 'Yes' : 'No'],
                            ].map(([label, value], k) => (
                              <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                                <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                                <span className="text-gray-900 dark:text-gray-100 font-medium text-right">{value}</span>
                              </div>
                            ))}
                          </div>
                          {stages.classification.triggers?.length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-1">
                              {stages.classification.triggers.map((t, k) => (
                                <span key={k} className="px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 rounded-full text-xs">{t}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )});

                      const scoi = idx++;
                      steps.push({ i: scoi, title: `${extraction ? '3' : '2'}. Confidence Scoring`, icon: Scale, body: (
                        <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60 text-xs">
                          {[
                            ['Final confidence', `${(stages.classification.confidence * 100).toFixed(1)}%`],
                            ...(stages.classification.confidence_factors ? [
                              ['Agreement (Dietterich)', `${(stages.classification.confidence_factors.agreement * 100).toFixed(0)}%`],
                              ['Evidence (Dempster-Shafer)', `${(stages.classification.confidence_factors.evidence * 100).toFixed(0)}%`],
                            ] : []),
                          ].map(([label, value], k) => (
                            <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                              <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                              <span className="text-gray-900 dark:text-gray-100 font-semibold text-right">{value}</span>
                            </div>
                          ))}
                        </div>
                      )});

                      const encI = idx++;
                      steps.push({ i: encI, title: `${extraction ? '4' : '3'}. Encryption`, icon: Lock, body: (
                        <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60 text-xs">
                          {[
                            ['Encrypted', stages.encryption.encrypted ? 'Yes' : 'No'],
                            ...(stages.encryption.encrypted
                              ? [
                                  ['Algorithm', stages.encryption.algorithm ?? '—'],
                                  ...(stages.encryption.key_id ? [['Key ID', stages.encryption.key_id]] : []),
                                ]
                              : [['Reason', stages.encryption.reason ?? 'C0/C1 stored as plaintext']]),
                          ].map(([label, value], k) => (
                            <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                              <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                              <span className="text-gray-900 dark:text-gray-100 font-medium text-right break-all">{value}</span>
                            </div>
                          ))}
                        </div>
                      )});

                      const stoI = idx++;
                      steps.push({ i: stoI, title: `${extraction ? '5' : '4'}. Storage`, icon: Database, body: (
                        <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60 text-xs">
                          {[
                            ['Stored', stages.storage.stored ? 'Yes' : 'No'],
                            ['Path', stages.storage.path ?? stages.storage.storage_path ?? '—'],
                          ].map(([label, value], k) => (
                            <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                              <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                              <span className="text-gray-900 dark:text-gray-100 font-medium text-right break-all">{value}</span>
                            </div>
                          ))}
                        </div>
                      )});

                      if (stages.access) {
                        const acI = idx++;
                        steps.push({ i: acI, title: `${extraction ? '6' : '5'}. Access Control`, icon: Shield, body: (
                          <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60 text-xs">
                            {[
                              ['User', stages.access.user_id],
                              ['Granted', stages.access.granted ? 'Yes' : 'No'],
                              ...(stages.access.reason ? [['Reason', stages.access.reason]] : []),
                            ].map(([label, value], k) => (
                              <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                                <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                                <span className="text-gray-900 dark:text-gray-100 font-medium text-right">{value}</span>
                              </div>
                            ))}
                          </div>
                        )});
                      }

                      const auI = idx;
                      steps.push({ i: auI, title: `${extraction ? (stages.access ? '7' : '6') : (stages.access ? '6' : '5')}. Audit Trail`, icon: ClipboardList, body: (
                        <div className="divide-y divide-gray-100 dark:divide-gray-700/60 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700/60 text-xs">
                          {[
                            ['Total events', String(stages.audit.total_events)],
                            ['Chain valid', stages.audit.chain_valid ? 'Yes' : 'No'],
                          ].map(([label, value], k) => (
                            <div key={k} className="flex justify-between gap-4 px-3 py-1.5 even:bg-gray-50/70 dark:even:bg-gray-800/40">
                              <span className="text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
                              <span className="text-gray-900 dark:text-gray-100 font-medium text-right">{value}</span>
                            </div>
                          ))}
                        </div>
                      )});

                      const stepPalette = [
                        { accent: 'bg-blue-500',   ring: 'border-l-blue-400',   iconBg: 'bg-blue-50 dark:bg-blue-900/20',   iconC: 'text-blue-500 dark:text-blue-400'   },
                        { accent: 'bg-violet-500', ring: 'border-l-violet-400', iconBg: 'bg-violet-50 dark:bg-violet-900/20',iconC: 'text-violet-500 dark:text-violet-400'},
                        { accent: 'bg-amber-500',  ring: 'border-l-amber-400',  iconBg: 'bg-amber-50 dark:bg-amber-900/20',  iconC: 'text-amber-500 dark:text-amber-400'  },
                        { accent: 'bg-orange-500', ring: 'border-l-orange-400', iconBg: 'bg-orange-50 dark:bg-orange-900/20',iconC: 'text-orange-500 dark:text-orange-400'},
                        { accent: 'bg-slate-500',  ring: 'border-l-slate-400',  iconBg: 'bg-slate-50 dark:bg-slate-900/20',  iconC: 'text-slate-500 dark:text-slate-400'  },
                        { accent: 'bg-green-500',  ring: 'border-l-green-400',  iconBg: 'bg-green-50 dark:bg-green-900/20',  iconC: 'text-green-500 dark:text-green-400'  },
                        { accent: 'bg-rose-500',   ring: 'border-l-rose-400',   iconBg: 'bg-rose-50 dark:bg-rose-900/20',    iconC: 'text-rose-500 dark:text-rose-400'    },
                      ];

                      return (
                        <div className="mt-5 pt-4 border-t border-gray-200 dark:border-gray-600">
                          <div className="flex items-center gap-2 mb-4">
                            <span className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-widest">Pipeline Details</span>
                            <div className="flex-1 h-px bg-gray-100 dark:bg-gray-700" />
                            <span className="text-xs text-green-600 dark:text-green-400 font-medium flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> {steps.length} stages completed
                            </span>
                          </div>
                          <div className="space-y-2">
                            {steps.map(({ i, title, icon: Icon, body }) => {
                              const pal = stepPalette[i % stepPalette.length];
                              return (
                                <div key={i} className={`rounded-xl border border-gray-200 dark:border-gray-700 border-l-4 ${pal.ring} overflow-hidden bg-white dark:bg-gray-800/60`}>
                                  <button
                                    type="button"
                                    onClick={() => toggleStep(file.id, i)}
                                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors"
                                  >
                                    <div className={`w-7 h-7 rounded-lg ${pal.iconBg} flex items-center justify-center flex-shrink-0`}>
                                      <Icon className={`w-3.5 h-3.5 ${pal.iconC}`} />
                                    </div>
                                    <span className="text-sm font-medium text-gray-800 dark:text-gray-100 flex-1">{title}</span>
                                    <span className="text-xs text-green-600 dark:text-green-400 font-medium flex items-center gap-1 mr-1">
                                      <CheckCircle2 className="w-3 h-3" /> Done
                                    </span>
                                    {isOpen(i)
                                      ? <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
                                      : <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />}
                                  </button>
                                  {isOpen(i) && (
                                    <div className="px-4 pb-4 pt-2 border-t border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/20">
                                      <div className="space-y-2">
                                        {body}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })()}

                    {file.error && (
                      <div className="mt-2 p-2 bg-red-100 dark:bg-red-900/20 rounded text-sm text-red-600 dark:text-red-400">
                        {file.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Settings Panel */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center gap-2 mb-4">
              <SettingsIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t('upload.classificationSettings')}
              </h3>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('upload.testAccessControl')}
                </label>
                <select
                  value={selectedUser}
                  onChange={(e) => setSelectedUser(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="">{t('upload.noUser')}</option>
                  {users.map((user) => (
                    <option key={user.user_id} value={user.user_id}>
                      {user.name} (Level {user.access_level})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Ground Truth Label (for evaluation)
                </label>
                <select
                  value={trueLabel}
                  onChange={(e) => setTrueLabel(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="">No label (skip evaluation)</option>
                  <option value="C0">C0 - Public</option>
                  <option value="C1">C1 - Internal</option>
                  <option value="C2">C2 - Confidential</option>
                  <option value="C3">C3 - Highly Sensitive</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Provide the correct classification to evaluate accuracy
                </p>
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  {t('upload.processingOptions')}
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    defaultChecked
                    disabled
                    className="w-4 h-4 text-[#1E3A8A] rounded"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    🤖 {t('upload.hybridAI')}
                  </span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    defaultChecked
                    disabled
                    className="w-4 h-4 text-[#1E3A8A] rounded"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {t('upload.autoEncrypt')}
                  </span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    defaultChecked
                    disabled
                    className="w-4 h-4 text-[#1E3A8A] rounded"
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {t('upload.generateAudit')}
                  </span>
                </label>
              </div>

              <button
                onClick={classifyFiles}
                disabled={!hasFilesToClassify || isClassifying}
                className="w-full px-6 py-3 bg-gradient-to-r from-[#1E3A8A] to-[#0891B2] text-white rounded-lg hover:opacity-90 transition-all font-medium disabled:opacity-50 disabled:cursor-not-allowed shadow-lg flex items-center justify-center gap-2"
              >
                {isClassifying ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    {t('upload.classifying')}
                  </>
                ) : (
                  <>
                    <Shield className="w-5 h-5" />
                    {t('upload.startClassification')}
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Generate Test Data Panel */}
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-xl p-6 border border-purple-200 dark:border-purple-800">
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h4 className="font-semibold text-purple-900 dark:text-purple-300">
                Generate Test Data
              </h4>
            </div>

            {datasetInfo && datasetInfo.exists && (
              <div className="mb-4 p-3 bg-white dark:bg-gray-800 rounded-lg text-xs">
                <p className="text-gray-600 dark:text-gray-400 mb-1">Current Dataset:</p>
                <p className="font-medium text-gray-900 dark:text-gray-100">{datasetInfo.count} documents</p>
                <div className="flex gap-2 mt-1 flex-wrap">
                  {datasetInfo.distribution && Object.entries(datasetInfo.distribution).map(([level, count]) => (
                    <span key={level} className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded">
                      {level}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-purple-700 dark:text-purple-400 mb-1">
                  Number of Documents
                </label>
                <input
                  type="number"
                  min={10}
                  max={500}
                  value={generateCount}
                  onChange={(e) => setGenerateCount(Math.min(500, Math.max(10, parseInt(e.target.value) || 100)))}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-purple-300 dark:border-purple-700 rounded-lg text-gray-900 dark:text-gray-100 text-sm"
                />
              </div>

              <button
                onClick={handleGenerateDataset}
                disabled={isGenerating}
                className="w-full px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-all font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Generate Dataset
                  </>
                )}
              </button>

              <p className="text-xs text-purple-600 dark:text-purple-400">
                Creates diverse Arabic/English documents with valid Egyptian National IDs, passports, IBANs, and salary data.
              </p>
            </div>
          </div>

          {/* Info Panel */}
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
            <h4 className="font-semibold text-blue-900 dark:text-blue-300 mb-2 flex items-center gap-2">
              <span>🤖</span> Hybrid AI Classification
            </h4>
            <ul className="text-sm text-blue-800 dark:text-blue-400 space-y-2">
              <li className="flex items-start gap-2">
                <span className="text-blue-600 dark:text-blue-500 mt-0.5">1.</span>
                <span>Document text extracted</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-600 dark:text-blue-500 mt-0.5">2.</span>
                <span>LLaMA 3 analyzes content contextually</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-600 dark:text-blue-500 mt-0.5">3.</span>
                <span>Security Rules check for sensitive patterns</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-600 dark:text-blue-500 mt-0.5">4.</span>
                <span>Final classification from agreement or escalation</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-blue-600 dark:text-blue-500 mt-0.5">5.</span>
                <span>C2/C3 docs encrypted with PQC (Kyber-768)</span>
              </li>
            </ul>
            <p className="text-xs text-blue-600 dark:text-blue-500 mt-3">
              Combines AI understanding with rule-based security checks
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
