import { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  Loader2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  Scale,
  Lock,
  Database,
  Shield,
  ClipboardList,
  AlertCircle,
  Cloud,
} from 'lucide-react';
import {
  classifyDocumentWithSteps,
  classifyPDFWithSteps,
  getUsers,
  getBackendSettings,
  type PipelineStepsResult,
  type User,
  type ClassificationSettings,
} from '../services/api';
import { SecurityBadge } from './SecurityBadge';
import { useAuth } from '../context/AuthContext';

type InputMode = 'text' | 'file';

export function PipelineStepsView() {
  const { user } = useAuth();
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [textInput, setTextInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [settings, setSettings] = useState<ClassificationSettings | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineStepsResult | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([0, 1]));
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [runTotalSeconds, setRunTotalSeconds] = useState<number | null>(null);
  const [, setClockTick] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const [usersData, settingsData] = await Promise.all([getUsers(), getBackendSettings()]);
        setUsers(usersData);
        setSettings(settingsData);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  // Drive live timer re-renders while the pipeline is running
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setClockTick(t => t + 1), 100);
    return () => clearInterval(id);
  }, [isRunning]);

  const toggleStep = (index: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const canRun =
    (inputMode === 'text' && textInput.trim().length > 0) || (inputMode === 'file' && selectedFile);
  const runPipeline = async () => {
    if (!canRun) return;
    const t0 = Date.now();
    setIsRunning(true);
    setRunStartedAt(t0);
    setRunTotalSeconds(null);
    setError(null);
    setResult(null);
    try {
      if (inputMode === 'file' && selectedFile) {
        const data = await classifyPDFWithSteps(
          selectedFile,
          selectedFile.name.replace(/\.[^/.]+$/, ''),
          selectedUser || undefined
        );
        setResult(data);
      } else {
        const data = await classifyDocumentWithSteps(
          textInput.trim(),
          `DOC_${Date.now()}`,
          selectedUser || undefined,
          settings ?? undefined
        );
        setResult(data);
      }
      setExpandedSteps(new Set([0, 1, 2, 3, 4, 5, 6]));
      setRunTotalSeconds((Date.now() - t0) / 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Pipeline failed');
      setRunTotalSeconds((Date.now() - t0) / 1000);
    } finally {
      setIsRunning(false);
    }
  };

  const stages = result?.pipeline_result?.stages;
  const extraction = result?.extraction;
  const hasExtractionStep = extraction != null;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <ClipboardList className="w-7 h-7 text-[#0891B2]" />
          Backend Pipeline Steps
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          Run classification and see every step the backend performs: extraction, LLM, rules,
          confidence, encryption, storage, and audit.
        </p>
      </div>

      {/* Input area */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-6 mb-6">
        <div className="flex gap-2 mb-4">
          <button
            type="button"
            onClick={() => setInputMode('text')}
            className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
              inputMode === 'text'
                ? 'bg-[#1E3A8A] text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}
          >
            <FileText className="w-4 h-4" />
            Paste text
          </button>
          <button
            type="button"
            onClick={() => setInputMode('file')}
            className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
              inputMode === 'file'
                ? 'bg-[#1E3A8A] text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}
          >
            <Upload className="w-4 h-4" />
            Upload PDF or image
          </button>
        </div>

        {inputMode === 'text' ? (
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Paste document text here..."
            className="w-full h-40 p-4 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-500 resize-none"
          />
        ) : (
          <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.bmp,.tiff,.tif"
              className="hidden"
              id="pipeline-file"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
            <label
              htmlFor="pipeline-file"
              className="cursor-pointer flex flex-col items-center gap-2 text-gray-600 dark:text-gray-400"
            >
              <Cloud className="w-10 h-10" />
              {selectedFile ? (
                <span className="font-medium text-gray-900 dark:text-gray-100">{selectedFile.name}</span>
              ) : (
                <span>Choose a PDF or image (PNG, JPEG, GIF, WebP, BMP, TIFF)</span>
              )}
            </label>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600 dark:text-gray-400">User (optional):</label>
            <select
              value={selectedUser}
              onChange={(e) => setSelectedUser(e.target.value)}
              className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 text-sm"
            >
              <option value="">None</option>
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.name} (Level {u.access_level})
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={runPipeline}
            disabled={!canRun || isRunning}
            className="px-6 py-2.5 bg-gradient-to-r from-[#1E3A8A] to-[#0891B2] text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="tabular-nums">
                  Running pipeline... {runStartedAt ? ((Date.now() - runStartedAt) / 1000).toFixed(1) : '0.0'}s
                </span>
              </>
            ) : (
              <>
                <Cpu className="w-5 h-5" />
                Run pipeline & show steps
              </>
            )}
          </button>

          {runTotalSeconds !== null && !isRunning && (
            <span className="text-sm text-gray-500 dark:text-gray-400 tabular-nums">
              ⏱ Completed in <span className="font-semibold text-gray-700 dark:text-gray-300">{runTotalSeconds.toFixed(1)}s</span>
            </span>
          )}
        </div>

        {/* Progress bar — visible while pipeline is running */}
        {isRunning && runStartedAt && (() => {
          const elapsed = (Date.now() - runStartedAt) / 1000;
          const pct = Math.min((elapsed / 60) * 90, 90);
          return (
            <div className="mt-4">
              <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-[#1E3A8A] to-[#0891B2] h-2 rounded-full transition-all duration-100"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {inputMode === 'file' && selectedFile && /\.(png|jpe?g|gif|webp|bmp|tiff?)$/i.test(selectedFile.name)
                  ? 'Running AI OCR + classification pipeline...'
                  : 'Running classification pipeline...'}
              </p>
            </div>
          );
        })()}
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-center gap-2 text-red-700 dark:text-red-300">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {result && stages && (() => {
        let stepIndex = 0;
        const steps: Array<{ index: number; title: string; icon: React.ElementType; children: React.ReactNode }> = [];

        if (hasExtractionStep && extraction) {
          steps.push({
            index: stepIndex++,
            title: extraction.source === 'image' ? '1. Image OCR extraction' : '1. Document text extraction',
            icon: FileText,
            children: (
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
                  <Row label="Source" value={extraction.source ?? 'pdf'} />
                  <Row label="Method" value={extraction.method} />
                  <Row label="Pages" value={String(extraction.pages)} />
                  <Row label="Text length" value={`${extraction.text_length} characters`} />
                  {extraction.direct_text_length != null && (
                    <Row label="Direct text (before OCR)" value={`${extraction.direct_text_length} chars`} />
                  )}
                  {extraction.ocr_text_length != null && (
                    <Row label="OCR text length" value={`${extraction.ocr_text_length} chars`} />
                  )}
                  <Row label="OCR used" value={extraction.ocr_used ? 'Yes' : 'No'} />
                  {extraction.language != null && <Row label="Language" value={extraction.language} />}
                  {extraction.dpi != null && <Row label="DPI" value={String(extraction.dpi)} />}
                  <Row label="Tesseract available" value={extraction.tesseract_available ? 'Yes' : 'No'} />
                  {extraction.tesseract_version != null && (
                    <Row label="Tesseract version" value={extraction.tesseract_version} />
                  )}
                  {extraction.source === 'pdf' && (
                    <>
                      {extraction.pdf2image_available != null && (
                        <Row label="pdf2image available" value={extraction.pdf2image_available ? 'Yes' : 'No'} />
                      )}
                      {extraction.pymupdf_available != null && (
                        <Row label="PyMuPDF available" value={extraction.pymupdf_available ? 'Yes' : 'No'} />
                      )}
                    </>
                  )}
                  {extraction.source === 'image' && (
                    <>
                      {extraction.image_mode != null && (
                        <Row label="Image mode" value={extraction.image_mode} />
                      )}
                      {extraction.image_size != null && extraction.image_size.length >= 2 && (
                        <Row label="Image size" value={`${extraction.image_size[0]} × ${extraction.image_size[1]}`} />
                      )}
                    </>
                  )}
                </div>
                {extraction.notes && (
                  <p className="text-gray-600 dark:text-gray-400 pt-2 border-t border-gray-200 dark:border-gray-600">
                    {extraction.notes}
                  </p>
                )}
                {extraction.error && (
                  <p className="text-amber-600 dark:text-amber-400">{extraction.error}</p>
                )}
              </div>
            ),
          });
        }

        const classificationNum = hasExtractionStep ? '2' : '1';
        steps.push({
          index: stepIndex++,
          title: `${classificationNum}. Hybrid classification`,
          icon: Cpu,
          children: (
            <div className="space-y-4 text-sm">
              <div>
                <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">LLaMA (LLM)</h4>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <SecurityBadge level={stages.classification.llm_classification as 'C0' | 'C1' | 'C2' | 'C3'} size="sm" />
                  {stages.classification.llm_raw_confidence != null && (
                    <span className="text-gray-500">
                      confidence {(stages.classification.llm_raw_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="text-gray-600 dark:text-gray-400">{stages.classification.reasoning}</p>
              </div>
              <div>
                <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Security rules</h4>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  {stages.classification.rules_classification ? (
                    <SecurityBadge level={stages.classification.rules_classification as 'C0' | 'C1' | 'C2' | 'C3'} size="sm" />
                  ) : (
                    <span className="text-gray-500">No triggers (defer to AI)</span>
                  )}
                  {stages.classification.triggers?.length > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs">
                      {stages.classification.triggers.join(', ')}
                    </span>
                  )}
                </div>
              </div>
              <div className="pt-2 border-t border-gray-200 dark:border-gray-600">
                <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Hybrid decision</h4>
                <div className="flex flex-wrap items-center gap-2">
                  <SecurityBadge level={stages.classification.classification} size="sm" />
                  <span className="px-2 py-1 rounded-lg bg-[#1E3A8A]/10 text-[#1E3A8A] dark:text-cyan-400 text-xs font-medium">
                    {stages.classification.method}
                  </span>
                  <span className="text-gray-500">
                    Agreement: {stages.classification.agreement ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
            </div>
          ),
        });

        steps.push({
          index: stepIndex++,
          title: 'Confidence scoring',
          icon: Scale,
          children: (
            <div className="space-y-2 text-sm">
              <Row
                label="Final confidence"
                value={`${(stages.classification.confidence * 100).toFixed(1)}%`}
              />
              {stages.classification.confidence_factors && (
                <>
                  <Row
                    label="Agreement (Dietterich)"
                    value={`${(stages.classification.confidence_factors.agreement * 100).toFixed(0)}%`}
                  />
                  <Row
                    label="Evidence (Dempster-Shafer)"
                    value={`${(stages.classification.confidence_factors.evidence * 100).toFixed(0)}%`}
                  />
                </>
              )}
              <p className="text-xs text-gray-500 mt-2">Formula: 0.50 × Agreement + 0.50 × Evidence</p>
              {stages.classification.confidence_explanation && (
                <p className="text-gray-600 dark:text-gray-400 mt-2">
                  {stages.classification.confidence_explanation}
                </p>
              )}
            </div>
          ),
        });

        steps.push({
          index: stepIndex++,
          title: 'Encryption',
          icon: Lock,
          children: (
            <div className="space-y-2 text-sm">
              <Row label="Encrypted" value={stages.encryption.encrypted ? 'Yes' : 'No'} />
              {stages.encryption.encrypted ? (
                <>
                  <Row label="Algorithm" value={stages.encryption.algorithm ?? '—'} />
                  {stages.encryption.key_id && (
                    <Row label="Key ID" value={stages.encryption.key_id} />
                  )}
                </>
              ) : (
                <Row label="Reason" value={stages.encryption.reason ?? 'C0/C1 stored as plaintext'} />
              )}
            </div>
          ),
        });

        steps.push({
          index: stepIndex++,
          title: 'Storage',
          icon: Database,
          children: (
            <div className="space-y-2 text-sm">
              <Row label="Stored" value={stages.storage.stored ? 'Yes' : 'No'} />
              <Row
                label="Path"
                value={stages.storage.path ?? stages.storage.storage_path ?? '—'}
              />
            </div>
          ),
        });

        if (stages.access) {
          steps.push({
            index: stepIndex++,
            title: 'Access control',
            icon: Shield,
            children: (
              <div className="space-y-2 text-sm">
                <Row label="User" value={stages.access.user_id} />
                <Row label="Granted" value={stages.access.granted ? 'Yes' : 'No'} />
                {stages.access.reason && (
                  <Row label="Reason" value={stages.access.reason} />
                )}
              </div>
            ),
          });
        }

        steps.push({
          index: stepIndex,
          title: 'Audit trail',
          icon: ClipboardList,
          children: (
            <div className="space-y-2 text-sm">
              <Row label="Total events" value={String(stages.audit.total_events)} />
              <Row label="Chain valid" value={stages.audit.chain_valid ? 'Yes' : 'No'} />
            </div>
          ),
        });

        return (
          <div className="space-y-0">
            <div className="relative pl-8 border-l-2 border-[#0891B2]/30 dark:border-cyan-500/30 ml-2">
              {steps.map(({ index, title, icon, children }) => (
                <StepCard
                  key={index}
                  index={index}
                  title={title}
                  icon={icon}
                  isExpanded={expandedSteps.has(index)}
                  onToggle={() => toggleStep(index)}
                >
                  {children}
                </StepCard>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-gray-900 dark:text-gray-100 font-medium break-all text-right">{value}</span>
    </div>
  );
}

function StepCard({
  index,
  title,
  icon: Icon,
  isExpanded,
  onToggle,
  children,
}: {
  index: number;
  title: string;
  icon: React.ElementType;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="relative mb-6 -ml-8">
      <div className="absolute left-0 w-4 h-4 rounded-full bg-[#0891B2] dark:bg-cyan-500 -translate-x-[9px] top-5 border-2 border-white dark:border-gray-800" />
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm overflow-hidden ml-6">
        <button
          type="button"
          onClick={onToggle}
          className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
          <Icon className="w-5 h-5 text-[#0891B2] flex-shrink-0" />
          <span className="font-medium text-gray-900 dark:text-gray-100 flex-1">{title}</span>
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          )}
        </button>
        {isExpanded && (
          <div className="px-4 pb-4 pt-0 border-t border-gray-100 dark:border-gray-700">
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
