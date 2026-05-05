import { useState, useEffect } from 'react';
import { FileText, AlertCircle, TrendingUp, Activity, RefreshCw, Lock, Play, Shield, Database, CheckCircle, Upload, ClipboardList, Cpu, Eye, Link } from 'lucide-react';
import { StatCard } from './StatCard';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { SecurityBadge } from './SecurityBadge';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { getStatistics, getAuditLogs, runEvaluation, getSignatureStatus, type Statistics, type AuditLog, type EvaluationResult } from '../services/api';

const classificationAccessLevel: Record<string, number> = {
  'C0': 1, 'C1': 2, 'C2': 3, 'C3': 4,
};

interface DashboardProps {
  onViewChange?: (view: string) => void;
}

export function Dashboard({ onViewChange }: DashboardProps) {
  const { user } = useAuth();
  const { t, isRTL } = useSettings();
  const userLevel = user?.access_level || 1;

  const [stats, setStats] = useState<Statistics | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [chainValid, setChainValid] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalResult, setEvalResult] = useState<EvaluationResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [sigStatus, setSigStatus] = useState<{ total_signed: number; algorithm: string; standard: string } | null>(null);

  const performanceData = evalResult ? [
    { class: 'C0', precision: evalResult.metrics.C0?.precision || 0, recall: evalResult.metrics.C0?.recall || 0, f1: evalResult.metrics.C0?.f1 || 0 },
    { class: 'C1', precision: evalResult.metrics.C1?.precision || 0, recall: evalResult.metrics.C1?.recall || 0, f1: evalResult.metrics.C1?.f1 || 0 },
    { class: 'C2', precision: evalResult.metrics.C2?.precision || 0, recall: evalResult.metrics.C2?.recall || 0, f1: evalResult.metrics.C2?.f1 || 0 },
    { class: 'C3', precision: evalResult.metrics.C3?.precision || 0, recall: evalResult.metrics.C3?.recall || 0, f1: evalResult.metrics.C3?.f1 || 0 },
  ] : [];

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, auditData, sigData] = await Promise.all([
        getStatistics(),
        getAuditLogs(user?.user_id),
        getSignatureStatus().catch(() => null),
      ]);
      setStats(statsData);
      setAuditLogs(auditData.logs);
      setChainValid(auditData.chain_valid);
      if (sigData) setSigStatus(sigData);
    } catch (err) {
      setError('Failed to connect to API. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  const handleRunEvaluation = async () => {
    setEvalLoading(true);
    setEvalError(null);
    try {
      const result = await runEvaluation(100);
      setEvalResult(result);
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : 'Evaluation failed');
    } finally {
      setEvalLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const canAccessClassification = (c: string) => userLevel >= (classificationAccessLevel[c] || 1);

  const allClassificationData = stats ? [
    { name: 'C0 - Public', value: stats.classifications.C0, color: '#60A5FA', key: 'C0' },
    { name: 'C1 - Internal', value: stats.classifications.C1, color: '#FBBF24', key: 'C1' },
    { name: 'C2 - Confidential', value: stats.classifications.C2, color: '#FB923C', key: 'C2' },
    { name: 'C3 - Highly Sensitive', value: stats.classifications.C3, color: '#EF4444', key: 'C3' },
  ] : [];

  const classificationData = allClassificationData.filter(item => canAccessClassification(item.key));
  const restrictedClassifications = allClassificationData.filter(item => !canAccessClassification(item.key));
  const accessibleDocsCount = classificationData.reduce((sum, item) => sum + item.value, 0);
  const totalDocs = stats?.documents_stored || 0;
  const encryptedDocs = stats?.encrypted_documents || 0;
  const c2c3Total = (stats?.classifications?.C2 || 0) + (stats?.classifications?.C3 || 0);
  const encryptionRate = totalDocs > 0 ? ((encryptedDocs / totalDocs) * 100).toFixed(0) : '0';

  const recentActivity = auditLogs
    .slice(-8)
    .reverse()
    .map((log, index) => ({
      id: index,
      type: log.event_type,
      doc: (log.data as Record<string, string>).document_id || '—',
      level: ((log.data as Record<string, string>).classification || '') as 'C0' | 'C1' | 'C2' | 'C3' | '',
      time: new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      date: new Date(log.timestamp).toLocaleDateString(),
      user: (log.data as Record<string, string>).user_id || (log.data as Record<string, string>).user_name || 'System',
    }))
    .filter(a => canAccessClassification(a.level || 'C0'));

  const eventTypeLabel: Record<string, string> = {
    DOCUMENT_CLASSIFICATION: 'Classified',
    DOCUMENT_CLASSIFIED: 'Classified',
    DOCUMENT_SIGNED: 'Signed',
    DOCUMENT_ENCRYPTED: 'Encrypted',
    ENCRYPTION_APPLIED: 'Encrypted',
    DOCUMENT_ENCRYPTED_STORAGE: 'Encrypted',
    DOCUMENT_VIEWED: 'Viewed',
    DOCUMENT_PREVIEWED: 'Previewed',
    DOCUMENT_DOWNLOADED: 'Downloaded',
    DOCUMENT_ACCESS: 'Accessed',
    ACCESS_GRANTED: 'Access Granted',
    ACCESS_DENIED: 'Access Denied',
    DOCUMENT_UPLOAD: 'Uploaded',
    USER_LOGIN: 'Login',
    GENESIS: 'Chain Init',
  };

  const eventTypeColor: Record<string, string> = {
    DOCUMENT_CLASSIFICATION: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    DOCUMENT_CLASSIFIED: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    DOCUMENT_SIGNED: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
    DOCUMENT_ENCRYPTED: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    ENCRYPTION_APPLIED: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    DOCUMENT_ENCRYPTED_STORAGE: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    DOCUMENT_VIEWED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    DOCUMENT_PREVIEWED: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
    DOCUMENT_DOWNLOADED: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    DOCUMENT_ACCESS: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    ACCESS_GRANTED: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    ACCESS_DENIED: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    DOCUMENT_UPLOAD: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
    USER_LOGIN: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-red-800 dark:text-red-300 mb-2">Connection Error</h3>
          <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
          <p className="text-sm text-red-500 dark:text-red-400 mb-4">
            Start the Flask API: <code className="bg-red-100 dark:bg-red-800 px-2 py-1 rounded">python3 web_api.py</code>
          </p>
          <button onClick={fetchData} className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-6 space-y-6 ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            Welcome back, {user?.name?.split(' ')[0]} 👋
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mt-1 text-sm">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            &nbsp;·&nbsp; Access Level {userLevel} — {user?.role}
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Security Pipeline Banner */}
      <div className="relative bg-gradient-to-br from-slate-50 via-blue-50/60 to-indigo-50/40 dark:from-[#07111f] dark:via-[#0d1f3c] dark:to-[#081a2e] border border-blue-100 dark:border-white/5 rounded-2xl p-6 shadow-sm dark:shadow-2xl overflow-hidden">
        {/* Decorative blobs */}
        <div className="absolute -top-10 -right-10 w-56 h-56 bg-blue-400/8 dark:bg-cyan-500/5 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute -bottom-10 left-20 w-56 h-56 bg-indigo-400/8 dark:bg-indigo-500/5 rounded-full blur-2xl pointer-events-none" />

        <div className="relative flex items-center justify-between mb-7">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-blue-100 dark:bg-cyan-500/15 rounded-xl border border-blue-200 dark:border-cyan-500/20">
              <Shield className="w-4 h-4 text-blue-600 dark:text-cyan-400" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white leading-tight">Document Security Pipeline</h3>
              <p className="text-xs text-gray-400 dark:text-white/35 mt-0.5">End-to-end quantum-safe processing</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse inline-block" />
            All systems operational
          </div>
        </div>

        <div className="relative grid grid-cols-5 gap-1">
          {/* Connecting track */}
          <div className="absolute top-[22px] left-[10%] right-[10%] h-px bg-gradient-to-r from-blue-300/40 via-violet-300/40 via-amber-300/40 via-emerald-300/40 to-rose-300/40 dark:from-blue-500/20 dark:via-violet-500/20 dark:via-amber-500/20 dark:via-emerald-500/20 dark:to-rose-500/20 pointer-events-none" />

          {[
            { num: '01', label: 'Extract',  sub: 'Qwen2.5-VL / OCR', icon: Eye,         lightBg: 'bg-blue-100',    lightRing: 'ring-blue-200',    lightIcon: 'text-blue-600',    lightNum: 'text-blue-400',    darkBg: 'dark:bg-blue-500/10',    darkRing: 'dark:ring-blue-500/30',    darkIcon: 'dark:text-blue-400',    darkNum: 'dark:text-blue-500/60'    },
            { num: '02', label: 'Classify', sub: 'LLaMA 3 + Rules',  icon: Cpu,         lightBg: 'bg-violet-100',  lightRing: 'ring-violet-200',  lightIcon: 'text-violet-600',  lightNum: 'text-violet-400',  darkBg: 'dark:bg-violet-500/10',  darkRing: 'dark:ring-violet-500/30',  darkIcon: 'dark:text-violet-400',  darkNum: 'dark:text-violet-500/60' },
            { num: '03', label: 'Sign',     sub: 'Dilithium3 · FIPS 204', icon: CheckCircle, lightBg: 'bg-emerald-100', lightRing: 'ring-emerald-200', lightIcon: 'text-emerald-600', lightNum: 'text-emerald-400', darkBg: 'dark:bg-emerald-500/10', darkRing: 'dark:ring-emerald-500/30', darkIcon: 'dark:text-emerald-400', darkNum: 'dark:text-emerald-500/60'},
            { num: '04', label: 'Encrypt',  sub: 'Kyber-768 + AES',  icon: Lock,        lightBg: 'bg-amber-100',   lightRing: 'ring-amber-200',   lightIcon: 'text-amber-600',   lightNum: 'text-amber-400',   darkBg: 'dark:bg-amber-500/10',   darkRing: 'dark:ring-amber-500/30',   darkIcon: 'dark:text-amber-400',   darkNum: 'dark:text-amber-500/60'  },
            { num: '05', label: 'Audit',    sub: 'Signed blockchain', icon: Database,    lightBg: 'bg-rose-100',    lightRing: 'ring-rose-200',    lightIcon: 'text-rose-600',    lightNum: 'text-rose-400',    darkBg: 'dark:bg-rose-500/10',    darkRing: 'dark:ring-rose-500/30',    darkIcon: 'dark:text-rose-400',    darkNum: 'dark:text-rose-500/60'   },
          ].map(({ num, label, sub, icon: Icon, lightBg, lightRing, lightIcon, lightNum, darkBg, darkRing, darkIcon, darkNum }) => (
            <div key={label} className="flex flex-col items-center text-center px-1">
              <div className={`relative w-11 h-11 rounded-2xl ${lightBg} ${darkBg} ring-1 ${lightRing} ${darkRing} flex items-center justify-center mb-3 z-10`}>
                <Icon className={`w-5 h-5 ${lightIcon} ${darkIcon}`} />
              </div>
              <span className={`text-[10px] font-bold tracking-widest ${lightNum} ${darkNum} mb-0.5`}>{num}</span>
              <span className="text-sm font-semibold text-gray-800 dark:text-white leading-tight">{label}</span>
              <span className="text-[11px] text-gray-400 dark:text-white/35 mt-0.5 leading-tight">{sub}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Documents Processed"
          value={loading ? '...' : String(stats?.documents_processed || 0)}
          icon={FileText}
          color="blue"
        />
        <StatCard
          title="Documents Signed"
          value={loading ? '...' : `${sigStatus?.total_signed ?? 0} / ${totalDocs}`}
          icon={Shield}
          color="green"
          trend={!loading && sigStatus ? { value: 'content integrity verified', isPositive: true } : undefined}
        />
        <StatCard
          title="C2 & C3 Encrypted"
          value={loading ? '...' : `${encryptedDocs} / ${c2c3Total}`}
          icon={Lock}
          color="amber"
          trend={!loading ? { value: 'sensitive docs PQC-protected', isPositive: encryptedDocs === c2c3Total } : undefined}
        />
        <StatCard
          title="Audit Events"
          value={loading ? '...' : String(stats?.audit?.total_events || 0)}
          icon={Database}
          color="red"
        />
      </div>

      {/* Main 3-Column Row: Classification | Recent Activity | Security Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: Classification Distribution */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Classification Distribution</h3>
            <Activity className="w-4 h-4 text-gray-400" />
          </div>
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={190}>
                <PieChart>
                  <Pie
                    data={classificationData}
                    cx="50%" cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name.split(' - ')[0]}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={72}
                    dataKey="value"
                  >
                    {classificationData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-3 space-y-2">
                {classificationData.map(item => (
                  <div key={item.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                      <span className="text-gray-600 dark:text-gray-400">{item.name}</span>
                    </div>
                    <span className="font-semibold text-gray-900 dark:text-gray-100">{item.value}</span>
                  </div>
                ))}
                {restrictedClassifications.length > 0 && (
                  <div className="pt-2 border-t border-gray-100 dark:border-gray-700 flex items-center gap-1.5 text-xs text-gray-400">
                    <Lock className="w-3 h-3" />
                    {restrictedClassifications.length} level(s) restricted by your access
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Center: Recent Activity (full height, more entries) */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Recent Activity</h3>
            {userLevel >= 5 && (
              <button onClick={() => onViewChange?.('audit')} className="text-xs text-[#0891B2] hover:underline">
                View all →
              </button>
            )}
          </div>
          <div className="flex-1 space-y-1 overflow-auto">
            {loading ? (
              <div className="h-full flex items-center justify-center">
                <RefreshCw className="w-7 h-7 text-gray-400 animate-spin" />
              </div>
            ) : recentActivity.length > 0 ? (
              recentActivity.map(activity => (
                <div key={activity.id} className="flex items-start gap-3 py-2.5 border-b border-gray-50 dark:border-gray-700/60 last:border-0">
                  <div className="w-7 h-7 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${eventTypeColor[activity.type] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>
                        {eventTypeLabel[activity.type] ?? activity.type}
                      </span>
                      {activity.level && <SecurityBadge level={activity.level} size="sm" showIcon={false} />}
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                      {activity.doc !== '—' && <span className="font-mono">{activity.doc}</span>}
                      {activity.doc !== '—' && ' · '}
                      <span className="font-medium text-gray-700 dark:text-gray-300">{activity.user}</span>
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">{activity.date} · {activity.time}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-gray-400 text-sm text-center">No activity yet — upload a document to start</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Blockchain Health + Digital Signature + Quick Actions */}
        <div className="flex flex-col gap-4">

          {/* Blockchain Health */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
            <div className="flex items-center gap-2 mb-3">
              <Link className="w-4 h-4 text-[#0891B2]" />
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Blockchain Audit</h3>
              <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${
                chainValid
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
              }`}>
                {chainValid ? '✓ Intact' : '✗ Tampered'}
              </span>
            </div>
            <div className="space-y-2">
              {[
                { label: 'Total Events', value: String(stats?.audit?.total_events || 0) },
                { label: 'Block Auth', value: 'Dilithium3 Signed' },
                { label: 'Hash', value: 'SHA-256' },
                { label: 'Structure', value: 'Merkle Tree' },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between text-xs">
                  <span className="text-gray-500 dark:text-gray-400">{label}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{loading ? '...' : value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Digital Signature */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4 text-indigo-500" />
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Digital Signature</h3>
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
                PQC
              </span>
            </div>
            <div className="space-y-2">
              {[
                { label: 'Algorithm', value: 'CRYSTALS-Dilithium3' },
                { label: 'Standard', value: 'NIST FIPS 204' },
                { label: 'Security Level', value: 'NIST Level 3' },
                { label: 'Signed Docs', value: String(sigStatus?.total_signed ?? '—') },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between text-xs">
                  <span className="text-gray-500 dark:text-gray-400">{label}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{loading ? '...' : value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-gradient-to-br from-[#1E3A8A] to-[#0891B2] rounded-xl p-5 text-white shadow-lg">
            <h3 className="font-semibold text-sm mb-3">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Upload', icon: Upload, view: 'upload' },
                ...(userLevel >= 5 ? [{ label: 'Audit Trail', icon: ClipboardList, view: 'audit' }] : []),
                { label: 'History', icon: Eye, view: 'history' },
                { label: 'Settings', icon: Activity, view: 'settings' },
              ].map(({ label, icon: Icon, view }) => (
                <button
                  key={view}
                  onClick={() => onViewChange?.(view)}
                  className="flex items-center gap-2 px-3 py-2.5 bg-white/10 hover:bg-white/20 rounded-lg transition-all text-xs font-medium backdrop-blur-sm border border-white/10"
                >
                  <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                  {label}
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* Bottom Row: Performance + Tech Stack */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* Performance Metrics (wider) */}
        <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Classification Performance</h3>
              {evalResult && (
                <p className="text-xs text-gray-500 mt-0.5">Accuracy: {evalResult.accuracy}% · {evalResult.total_docs} docs</p>
              )}
            </div>
            <button
              onClick={handleRunEvaluation}
              disabled={evalLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-all disabled:opacity-50 text-sm"
            >
              <Play className={`w-3.5 h-3.5 ${evalLoading ? 'animate-pulse' : ''}`} />
              {evalLoading ? 'Running...' : 'Evaluate'}
            </button>
          </div>
          {evalLoading ? (
            <div className="h-[200px] flex flex-col items-center justify-center text-gray-400">
              <RefreshCw className="w-10 h-10 mb-3 animate-spin opacity-40" />
              <p className="text-sm">Running evaluation...</p>
            </div>
          ) : performanceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.15} />
                <XAxis dataKey="class" stroke="#6B7280" tick={{ fontSize: 12 }} />
                <YAxis stroke="#6B7280" domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                  formatter={(v: number) => `${v}%`}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="precision" name="Precision %" fill="#10B981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="recall" name="Recall %" fill="#0891B2" radius={[4, 4, 0, 0]} />
                <Bar dataKey="f1" name="F1 %" fill="#1E3A8A" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex flex-col items-center justify-center text-gray-400">
              <TrendingUp className="w-10 h-10 mb-3 opacity-25" />
              <p className="text-sm font-medium">No Evaluation Data</p>
              <p className="text-xs mt-1 text-center">Click Evaluate to run precision, recall & F1</p>
            </div>
          )}
        </div>

        {/* Technology Stack (full remaining width) */}
        <div className="lg:col-span-3 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-4 h-4 text-gray-500" />
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Technology Stack</h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {[
              { label: 'CRYSTALS-Dilithium3', sub: 'Post-Quantum Signature', color: 'border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300' },
              { label: 'NIST FIPS 204', sub: 'ML-DSA-65 Standard', color: 'border-indigo-100 dark:border-indigo-800/50 bg-indigo-50/50 dark:bg-indigo-900/10 text-indigo-600 dark:text-indigo-400' },
              { label: 'Qwen2.5-VL', sub: 'Vision-Language OCR', color: 'border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' },
              { label: 'LLaMA 3', sub: 'Hybrid AI Classifier', color: 'border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300' },
              { label: 'AES-256 / PQC', sub: 'Document Encryption', color: 'border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300' },
              { label: 'Signed Blockchain', sub: 'Dilithium3 Block Auth', color: 'border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-900/20 text-rose-700 dark:text-rose-300' },
              { label: 'Merkle Tree', sub: 'Block Integrity', color: 'border-rose-100 dark:border-rose-800/50 bg-rose-50/50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400' },
              { label: 'Tesseract OCR', sub: 'Arabic + English Fallback', color: 'border-cyan-200 dark:border-cyan-800 bg-cyan-50 dark:bg-cyan-900/20 text-cyan-700 dark:text-cyan-300' },
              { label: 'RBAC — 5 Levels', sub: 'Role-Based Access', color: 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' },
            ].map(({ label, sub, color }) => (
              <div key={label} className={`flex flex-col px-3 py-2.5 rounded-lg border text-xs ${color}`}>
                <span className="font-semibold leading-tight">{label}</span>
                <span className="opacity-70 mt-0.5 leading-tight">{sub}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
