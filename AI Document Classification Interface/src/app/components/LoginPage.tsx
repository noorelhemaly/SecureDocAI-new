import { useState, useEffect } from 'react';
import { Shield, Lock, User, AlertCircle, Loader2, FileText, Key, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { checkHealth } from '../services/api';

export function LoginPage() {
  const { users, login, isLoading } = useAuth();
  const [selectedUser, setSelectedUser] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  // Check API status on mount
  useEffect(() => {
    checkHealth().then(ok => {
      setApiStatus(ok ? 'online' : 'offline');
    });
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

    if (!selectedUser) {
      setError('Please select a user');
      return;
    }

    // Demo: password is user_id (e.g., U001)
    if (password !== selectedUser) {
      setError('Invalid password. Hint: Use the User ID as password');
      return;
    }

    setIsConnecting(true);

    // Check API connection first
    const apiOk = await checkHealth();
    if (!apiOk) {
      setError('Cannot connect to API server. Please start the Flask server.');
      setIsConnecting(false);
      return;
    }

    const success = await login(selectedUser);
    if (!success) {
      setError('Login failed. Please try again.');
    }
    setIsConnecting(false);
  };

  const getAccessLevelColor = (level: number) => {
    switch (level) {
      case 1: return 'text-blue-500';
      case 2: return 'text-green-500';
      case 3: return 'text-yellow-500';
      case 4: return 'text-orange-500';
      case 5: return 'text-red-500';
      default: return 'text-gray-500';
    }
  };

  const getAccessLevelBadge = (level: number) => {
    const labels = ['', 'Public Only', 'Internal', 'Confidential', 'Sensitive', 'Full Access'];
    const colors = [
      '',
      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
      'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    ];
    return { label: labels[level] || 'Unknown', color: colors[level] || colors[0] };
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#1E3A8A] via-[#1E3A8A] to-[#0891B2] flex items-center justify-center">
        <Loader2 className="w-12 h-12 text-white animate-spin" />
      </div>
    );
  }

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
        {/* Glowing circuit dots */}
        {[
          [12,12],[60,60],[108,12],[156,60],[204,12],[252,60],[300,12],[348,60],[396,12],[444,60],[492,12],[540,60],
          [36,108],[84,156],[132,108],[180,156],[228,108],[276,156],[324,108],[372,156],[420,108],[468,156],[516,108],
          [12,204],[60,252],[108,204],[156,252],[204,204],[252,252],[300,204],[348,252],[396,204],[444,252],[492,204],
          [36,300],[84,348],[132,300],[180,348],[228,300],[276,348],[324,300],[372,348],[420,300],[468,348],[516,300],
        ].map(([cx, cy], i) => (
          <circle
            key={i}
            cx={cx} cy={cy} r="2"
            fill="#0BCBE8"
            style={{
              animation: `dotPulse ${2 + (i % 4) * 0.5}s ease-in-out infinite`,
              animationDelay: `${(i % 7) * 0.3}s`,
            }}
          />
        ))}
      </svg>
      {/* Radial glow blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-cyan-400/5 rounded-full blur-2xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 overflow-hidden flex items-center justify-center logo-glow" style={{ width: '140px', height: '140px' }}>
            <img
              src="/logo.png"
              alt="SecureDoc AI"
              style={{ width: '280px', maxWidth: 'none', objectFit: 'contain' }}
            />
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
            {apiStatus === 'offline' && 'API Server Offline - Start web_api.py'}
            {apiStatus === 'checking' && 'Checking connection...'}
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            {/* User Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <User className="w-4 h-4 inline mr-2" />
                Select User
              </label>
              <select
                value={selectedUser}
                onChange={(e) => setSelectedUser(e.target.value)}
                className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-xl text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-[#0891B2] focus:border-transparent transition-all"
              >
                <option value="">Choose a user...</option>
                {users.map((user) => {
                  const badge = getAccessLevelBadge(user.access_level);
                  return (
                    <option key={user.user_id} value={user.user_id}>
                      {user.name} - {user.role} (Level {user.access_level})
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Selected User Info */}
            {selectedUser && (
              <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                {(() => {
                  const user = users.find(u => u.user_id === selectedUser);
                  if (!user) return null;
                  const badge = getAccessLevelBadge(user.access_level);
                  return (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600 dark:text-gray-400">User ID</span>
                        <span className="font-mono text-sm font-medium text-gray-900 dark:text-gray-100">{user.user_id}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600 dark:text-gray-400">Department</span>
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{user.department || 'N/A'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600 dark:text-gray-400">Access Level</span>
                        <span className={`text-xs px-2 py-1 rounded-full ${badge.color}`}>
                          Level {user.access_level} - {badge.label}
                        </span>
                      </div>
                      <div className="pt-2 border-t border-gray-200 dark:border-gray-600">
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          Can access: {['C0', 'C1', 'C2', 'C3'].slice(0, user.access_level).join(', ') || 'None'}
                        </span>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

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
                Demo: Use User ID as password (e.g., U001)
              </p>
            </div>

            {/* Error Message */}
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
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <Lock className="w-5 h-5" />
                  Sign In
                </>
              )}
            </button>
          </form>

          {/* Footer Info */}
          <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-center gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" />
                LLaMA 3 Powered
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Shield className="w-3 h-3" />
                PQC Encrypted
              </span>
            </div>
          </div>
        </div>

        {/* Attribution */}
        <div className="text-center mt-6 text-blue-200 text-sm">
          <p>Coventry University - The Knowledge Hub</p>
          <p className="text-blue-300/70 text-xs mt-1">Noor Elhemaly (202300013) • Dr. Haitham Ghalwash</p>
        </div>
      </div>
    </div>
  );
}
