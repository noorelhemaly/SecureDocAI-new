import {
  LayoutDashboard,
  Upload,
  History,
  Settings,
  User,
  LogOut,
  ChevronDown,
  Moon,
  Sun,
  Key,
  Link2,
} from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';

interface NavigationProps {
  activeView: string;
  onViewChange: (view: string) => void;
  darkMode: boolean;
  onToggleDarkMode: () => void;
}

export function Navigation({ activeView, onViewChange, darkMode, onToggleDarkMode }: NavigationProps) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { user, logout } = useAuth();
  const { t, isRTL } = useSettings();

  const baseItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { id: 'upload', label: t('nav.upload'), icon: Upload },
    { id: 'history', label: t('nav.history'), icon: History },
  ];

  // Audit trail before settings, Level 5 only
  const navItems = [
    ...baseItems,
    ...(user?.access_level === 5
      ? [{ id: 'audit', label: 'Audit Trail', icon: Link2 }]
      : []),
    { id: 'settings', label: t('nav.settings'), icon: Settings },
  ];

  const getAccessLevelBadge = (level: number) => {
    const labels = ['', 'C0', 'C0-C1', 'C0-C2', 'C0-C3', 'Full'];
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

  const handleLogout = () => {
    setShowUserMenu(false);
    logout();
  };

  const badge = user ? getAccessLevelBadge(user.access_level) : null;

  return (
    <nav className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-50 shadow-sm">
      <div className="mx-auto px-6">
        <div className="flex items-center justify-between h-20">
          {/* Logo and Brand */}
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 overflow-hidden flex-shrink-0 flex items-center justify-center">
              <img
                src="/logo.png"
                alt="SecureDoc AI"
                className="logo-glow"
                style={{ width: '230%', maxWidth: 'none' }}
              />
            </div>
            <h1 className="text-2xl font-black font-mono leading-none tracking-widest uppercase flex items-baseline gap-0">
              <span className="text-gray-900 dark:text-gray-100">SECURE</span>
              <span style={{ color: '#0BCBE8', filter: 'drop-shadow(0 0 8px rgba(11,203,232,0.7))' }}>DOC</span>
              <span className="text-gray-900 dark:text-gray-100">&nbsp;AI</span>
            </h1>
          </div>

          {/* Navigation Menu */}
          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => onViewChange(item.id)}
                  className={`relative flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                    activeView === item.id
                      ? 'text-[#0BCBE8]'
                      : 'text-gray-600 dark:text-gray-300 hover:text-[#0BCBE8] hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{item.label}</span>
                  {activeView === item.id && (
                    <span
                      className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
                      style={{
                        background: 'linear-gradient(90deg, #0891B2, #0BCBE8)',
                        boxShadow: '0 0 8px rgba(11,203,232,0.7)',
                        animation: 'navUnderlineIn 0.2s ease-out both',
                        transformOrigin: 'left',
                      }}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* User Profile and Actions */}
          <div className="flex items-center gap-3">
            {/* Access Level Badge */}
            {user && badge && (
              <div className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-full text-xs ${badge.color}`}>
                <Key className="w-3 h-3" />
                Level {user.access_level}
              </div>
            )}

            <button
              onClick={onToggleDarkMode}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-all"
            >
              {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#0891B2] flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {user?.name?.split(' ').map(n => n[0]).join('') || 'U'}
                  </span>
                </div>
                <div className="text-left hidden lg:block">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{user?.name || 'Unknown'}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{user?.role || 'Guest'}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 py-2 overflow-hidden">
                  {/* User Info Header */}
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#1E3A8A] to-[#0891B2] flex items-center justify-center">
                        <span className="text-white font-medium">
                          {user?.name?.split(' ').map(n => n[0]).join('') || 'U'}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">{user?.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{user?.user_id}</p>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span className="text-gray-500 dark:text-gray-400 block">Role</span>
                        <span className="font-medium text-gray-900 dark:text-gray-100">{user?.role}</span>
                      </div>
                      <div className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span className="text-gray-500 dark:text-gray-400 block">Access</span>
                        <span className={`font-medium px-1.5 py-0.5 rounded ${badge?.color}`}>
                          Level {user?.access_level}
                        </span>
                      </div>
                    </div>
                    {user?.department && (
                      <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        Department: {user.department}
                      </div>
                    )}
                  </div>

                  {/* Menu Items */}
                  <div className="py-1">
                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        onViewChange('settings');
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      <User className="w-4 h-4" />
                      {t('nav.profileSettings')}
                    </button>
                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        onViewChange('settings');
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      <Settings className="w-4 h-4" />
                      {t('nav.systemSettings')}
                    </button>
                  </div>

                  <div className="border-t border-gray-200 dark:border-gray-700 py-1">
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <LogOut className="w-4 h-4" />
                      {t('nav.signOut')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
