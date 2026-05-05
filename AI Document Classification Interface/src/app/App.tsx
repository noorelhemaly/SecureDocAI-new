import { useState, useEffect, Component, ReactNode } from 'react';
import { Navigation } from './components/Navigation';
import { Dashboard } from './components/Dashboard';
import { UploadView } from './components/UploadView';
import { HistoryView } from './components/HistoryView';
import { AuditTrailView } from './components/AuditTrailView';
import { SettingsView } from './components/SettingsView';
import { PipelineStepsView } from './components/PipelineStepsView';
import { LoginPage } from './components/LoginPage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { SettingsProvider } from './context/SettingsContext';
import { Loader2, ShieldOff, AlertTriangle } from 'lucide-react';

// ── Error Boundary ────────────────────────────────────────────────────────────
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-8">
          <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Something went wrong</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              {(this.state.error as Error).message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.hash = 'dashboard'; }}
              className="px-5 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1E3A8A]/90 transition-colors text-sm"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const VALID_VIEWS = ['dashboard', 'upload', 'history', 'audit', 'settings', 'pipeline-steps'];

// Minimum access level required for each view (default 1)
const VIEW_ACCESS: Record<string, number> = {
  audit: 5,
};

function getViewFromHash(): string {
  const hash = window.location.hash.replace('#', '');
  return VALID_VIEWS.includes(hash) ? hash : 'dashboard';
}

function AppContent() {
  const [activeView, setActiveView] = useState(getViewFromHash);
  const [darkMode, setDarkMode] = useState(false);
  const { isAuthenticated, isLoading, user } = useAuth();

  useEffect(() => {
    const isDark = localStorage.getItem('darkMode') === 'true';
    setDarkMode(isDark);
    if (isDark) {
      document.documentElement.classList.add('dark');
    }
  }, []);

  // Sync hash with auth state
  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      // Save the intended page so we can redirect after login
      const currentHash = window.location.hash.replace('#', '');
      if (currentHash && VALID_VIEWS.includes(currentHash)) {
        sessionStorage.setItem('postLoginRedirect', currentHash);
      }
      window.location.hash = 'login';
    } else {
      // Just logged in — redirect to saved page or dashboard
      if (window.location.hash === '#login' || window.location.hash === '') {
        const redirect = sessionStorage.getItem('postLoginRedirect') || 'dashboard';
        sessionStorage.removeItem('postLoginRedirect');
        window.location.hash = redirect;
        setActiveView(redirect);
      }
    }
  }, [isAuthenticated, isLoading]);

  useEffect(() => {
    const onHashChange = () => {
      const view = getViewFromHash();
      setActiveView(view);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const handleViewChange = (view: string) => {
    window.location.hash = view;
    setActiveView(view);
  };

  const handleToggleDarkMode = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    localStorage.setItem('darkMode', String(newDarkMode));
    if (newDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  const renderView = () => {
    const requiredLevel = VIEW_ACCESS[activeView] ?? 1;
    const userLevel = user?.access_level ?? 0;

    if (userLevel < requiredLevel) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] gap-6 p-8">
          <div className="bg-red-100 dark:bg-red-900/20 p-5 rounded-full">
            <ShieldOff className="w-12 h-12 text-red-600 dark:text-red-400" />
          </div>
          <div className="text-center max-w-md">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Access Denied</h2>
            <p className="text-gray-500 dark:text-gray-400">
              You don't have permission to access this page. Contact your administrator if you believe this is a mistake.
            </p>
          </div>
          <button
            onClick={() => handleViewChange('dashboard')}
            className="px-5 py-2 bg-[#1E3A8A] text-white rounded-lg hover:bg-[#1e3a8a]/90 transition-colors text-sm"
          >
            Go to Dashboard
          </button>
        </div>
      );
    }

    switch (activeView) {
      case 'dashboard':
        return <Dashboard onViewChange={handleViewChange} />;
      case 'upload':
        return <UploadView />;
      case 'history':
        return <HistoryView onViewChange={handleViewChange} />;
      case 'audit':
        return <AuditTrailView />;
      case 'settings':
        return <SettingsView />;
      case 'pipeline-steps':
        return <UploadView />;
      default:
        return <Dashboard />;
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#1E3A8A] via-[#1E3A8A] to-[#0891B2] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-white animate-spin mx-auto mb-4" />
          <p className="text-white/80">Loading SecureDoc AI...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      <Navigation
        activeView={activeView}
        onViewChange={handleViewChange}
        darkMode={darkMode}
        onToggleDarkMode={handleToggleDarkMode}
      />
      <main className="min-h-[calc(100vh-5rem)]">
        <div key={activeView} className="page-fade">
          {renderView()}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <SettingsProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </SettingsProvider>
    </ErrorBoundary>
  );
}
