import { useState, useEffect } from 'react';
import { Shield, Lock, User, AlertCircle, Loader2, FileText, Key, Eye, EyeOff, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { checkHealth } from '../services/api';

const DEMO_USERS = [
  { group: 'Finance',    username: 'finance_staff',            label: 'Finance Staff',            role: 'Staff',                   level: 2 },
  { group: 'Finance',    username: 'finance_analyst',          label: 'Finance Analyst',           role: 'Analyst',                 level: 3 },
  { group: 'Finance',    username: 'finance_manager',          label: 'Finance Manager',           role: 'Finance Manager',         level: 4 },
  { group: 'Marketing',  username: 'marketing_staff',          label: 'Marketing Staff',           role: 'Staff',                   level: 2 },
  { group: 'Marketing',  username: 'marketing_analyst',        label: 'Marketing Analyst',         role: 'Analyst',                 level: 3 },
  { group: 'Marketing',  username: 'marketing_manager',        label: 'Marketing Manager',         role: 'Manager',                 level: 4 },
  { group: 'HR',         username: 'hr_staff',                 label: 'HR Staff',                  role: 'HR Staff',                level: 2 },
  { group: 'HR',         username: 'hr_analyst',               label: 'HR Analyst',                role: 'Analyst',                 level: 3 },
  { group: 'HR',         username: 'hr_manager',               label: 'HR Manager',                role: 'HR Manager',              level: 4 },
  { group: 'Operations', username: 'customer_service_officer', label: 'Customer Service Officer',  role: 'Customer Service Officer', level: 2 },
  { group: 'Operations', username: 'branch_operations',        label: 'Branch Operations Officer', role: 'Operations Officer',      level: 3 },
  { group: 'Operations', username: 'branch_manager',           label: 'Branch Manager',            role: 'Branch Manager',          level: 4 },
  { group: 'Admin',      username: 'dpo',                      label: 'Data Protection Officer',   role: 'DPO',                     level: 4 },
  { group: 'Admin',      username: 'ciso',                     label: 'CISO',                      role: 'CISO',                    level: 5 },
  { group: 'Other',      username: 'viewer',                   label: 'Public Viewer',             role: 'Public',                  level: 1 },
];

const GROUPS = ['Finance', 'Marketing', 'HR', 'Operations', 'Admin', 'Other'];

const LEVEL_COLORS: Record<number, string> = {
  1: 'text-gray-400',
  2: 'text-blue-500',
  3: 'text-yellow-500',
  4: 'text-orange-500',
  5: 'text-red-500',
};

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('demo123');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  const selectedUser = DEMO_USERS.find(u => u.username === username) ?? null;

  const handleSelectUser = (u: string) => {
    setUsername(u);
    setPassword('demo123');
    setError('');
  };

  useEffect(() => {
    checkHealth().then(ok => setApiStatus(ok ? 'online' : 'offline'));
  }, []);

  const SUBTITLE = 'Policy-Aware Document Classification System';
  const [typedText, setTypedText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  useEffect(() => {
    let i = 0;
    const iv = setInterval(() => {
      setTypedText(SUBTITLE.slice(0, i + 1));
      i++;
      if (i >= SUBTITLE.length) clearInterval(iv);
    }, 40);
    const cursorIv = setInterval(() => setShowCursor(c => !c), 530);
    return () => { clearInterval(iv); clearInterval(cursorIv); };
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim()) {
      setError('Please select an account');
      return;
    }
    if (!password) {
      setError('Please enter your password');
      return;
    }

    setIsConnecting(true);

    const apiOk = await checkHealth();
    if (!apiOk) {
      setError('Cannot connect to API server. Please start the Flask server (python web_api.py).');
      setIsConnecting(false);
      return;
    }

    const result = await login(username.trim(), password);
    if (!result.success) {
      setError(result.error || 'Login failed. Please try again.');
    }
    setIsConnecting(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#060e1f] via-[#0d1b3e] to-[#061629] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated circuit grid background */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="rgba(11,203,232,0.08)" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" style={{ animation: 'gridFloat 4s ease-in-out infinite' }} />
        {[
          [12,12],[60,60],[108,12],[156,60],[204,12],[252,60],[300,12],[348,60],[396,12],[444,60],[492,12],[540,60],
          [36,108],[84,156],[132,108],[180,156],[228,108],[276,156],[324,108],[372,156],[420,108],[468,156],[516,108],
          [12,204],[60,252],[108,204],[156,252],[204,204],[252,252],[300,204],[348,252],[396,204],[444,252],[492,204],
          [36,300],[84,348],[132,300],[180,348],[228,300],[276,348],[324,300],[372,348],[420,300],[468,348],[516,300],
        ].map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r="2" fill="#0BCBE8"
            style={{ animation: `dotPulse ${2 + (i % 4) * 0.5}s ease-in-out infinite`, animationDelay: `${(i % 7) * 0.3}s` }}
          />
        ))}
      </svg>
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-cyan-400/5 rounded-full blur-2xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 overflow-hidden flex items-center justify-center logo-glow" style={{ width: '140px', height: '140px' }}>
            <img src="/logo.png" alt="SecureDoc AI" style={{ width: '280px', maxWidth: 'none', objectFit: 'contain' }} />
          </div>
          <h1 className="text-3xl font-black font-mono tracking-widest uppercase text-white mb-2">
            SECURE<span className="text-[#0BCBE8]" style={{ filter: 'drop-shadow(0 0 8px rgba(11,203,232,0.7))' }}>DOC</span> AI
          </h1>
          <p className="text-cyan-300/80 font-mono text-sm tracking-wider">
            {typedText}<span style={{ opacity: showCursor ? 1 : 0 }}>|</span>
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8">
          {/* API Status */}
          <div className={`flex items-center gap-2 text-sm mb-6 p-3 rounded-lg ${
            apiStatus === 'online'
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
              : apiStatus === 'offline'
              ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
              : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              apiStatus === 'online' ? 'bg-green-500' : apiStatus === 'offline' ? 'bg-red-500' : 'bg-gray-400'
            }`} />
            {apiStatus === 'online' && 'API Server Connected'}
            {apiStatus === 'offline' && 'API Server Offline — Start web_api.py'}
            {apiStatus === 'checking' && 'Checking connection...'}
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            {/* User Dropdown */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <User className="w-4 h-4 inline mr-2" />
                Select Account
              </label>
              <div className="relative">
                <select
                  value={username}
                  onChange={(e) => handleSelectUser(e.target.value)}
                  className="w-full appearance-none px-4 py-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-xl text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-[#0891B2] focus:border-transparent transition-all pr-10 cursor-pointer"
                >
                  <option value="">— Choose a user —</option>
                  {GROUPS.map(group => (
                    <optgroup key={group} label={group}>
                      {DEMO_USERS.filter(u => u.group === group).map(u => (
                        <option key={u.username} value={u.username}>
                          {u.label} (L{u.level} · {u.role})
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              </div>

              {/* Selected user badge */}
              {selectedUser && (
                <div className="mt-2 flex items-center gap-2 px-3 py-1.5 bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800 rounded-lg text-xs">
                  <span className="font-mono text-gray-600 dark:text-gray-300">{selectedUser.username}</span>
                  <span className="text-gray-400">·</span>
                  <span className={`font-semibold ${LEVEL_COLORS[selectedUser.level]}`}>Level {selectedUser.level}</span>
                  <span className="text-gray-400">·</span>
                  <span className="text-gray-500 dark:text-gray-400">{selectedUser.group} dept</span>
                </div>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Key className="w-4 h-4 inline mr-2" />
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  autoComplete="current-password"
                  className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-xl text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-[#0891B2] focus:border-transparent transition-all pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                All demo accounts use password <span className="font-mono font-semibold">demo123</span>
              </p>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-lg text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Login Button */}
            <button
              type="submit"
              disabled={isConnecting || apiStatus === 'offline'}
              className="w-full py-3 px-4 bg-gradient-to-r from-[#1E3A8A] to-[#0891B2] text-white rounded-xl font-medium hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg"
            >
              {isConnecting ? (
                <><Loader2 className="w-5 h-5 animate-spin" />Connecting...</>
              ) : (
                <><Lock className="w-5 h-5" />Sign In</>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-5 pt-5 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-center gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span className="flex items-center gap-1"><FileText className="w-3 h-3" />LLaMA 3 Powered</span>
              <span>•</span>
              <span className="flex items-center gap-1"><Shield className="w-3 h-3" />PQC Encrypted</span>
            </div>
          </div>
        </div>

        <div className="text-center mt-6 text-blue-200 text-sm">
          <p>Coventry University - The Knowledge Hub</p>
          <p className="text-blue-300/70 text-xs mt-1">Noor Elhemaly (202300013) • Dr. Haitham Ghalwash</p>
        </div>
      </div>
    </div>
  );
}
