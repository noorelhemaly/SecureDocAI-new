import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { translations, type TranslationKey, type Language } from '../i18n/translations';

// Settings types
export interface AppSettings {
  // General
  language: 'en' | 'ar' | 'both';
  layoutDirection: 'ltr' | 'rtl';
  timezone: string;
  dateFormat: 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD';

  // Classification
  confidenceThreshold: number;
  hybridMode: 'conservative' | 'balanced' | 'aggressive';
  autoEscalate: boolean;
  requireC3Review: boolean;
  realtimeNotifications: boolean;

  // Security
  sessionTimeout: number;
  require2FA: boolean;
  autoEncryptC2C3: boolean;
  auditLogging: boolean;
  restrictC3Downloads: boolean;

  // Integrity Protection
  enableBlockchainProtection: boolean;
  enableDigitalSignature: boolean;

  // Notifications
  notifyClassificationComplete: boolean;
  notifyHighRisk: boolean;
  notifyDisagreement: boolean;
  notifySystemUpdates: boolean;

  // Compliance
  generateComplianceReports: boolean;
  enableDSARWorkflow: boolean;
}

const defaultSettings: AppSettings = {
  // General
  language: 'en',
  layoutDirection: 'ltr',
  timezone: 'Africa/Cairo',
  dateFormat: 'DD/MM/YYYY',

  // Classification
  confidenceThreshold: 85,
  hybridMode: 'conservative',
  autoEscalate: true,
  requireC3Review: true,
  realtimeNotifications: false,

  // Security
  sessionTimeout: 30,
  require2FA: true,
  autoEncryptC2C3: true,
  auditLogging: true,
  restrictC3Downloads: false,

  // Integrity Protection
  enableBlockchainProtection: false,
  enableDigitalSignature: false,

  // Notifications
  notifyClassificationComplete: true,
  notifyHighRisk: true,
  notifyDisagreement: false,
  notifySystemUpdates: true,

  // Compliance
  generateComplianceReports: true,
  enableDSARWorkflow: true,
};

interface SettingsContextType {
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  resetSettings: () => void;
  formatDate: (date: Date | string) => string;
  formatTime: (date: Date | string) => string;
  t: (key: TranslationKey) => string;
  isRTL: boolean;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(() => {
    // Load from localStorage on init
    const saved = localStorage.getItem('appSettings');
    if (saved) {
      try {
        return { ...defaultSettings, ...JSON.parse(saved) };
      } catch {
        return defaultSettings;
      }
    }
    return defaultSettings;
  });

  // Save to localStorage when settings change
  useEffect(() => {
    localStorage.setItem('appSettings', JSON.stringify(settings));

    // Apply layout direction
    document.documentElement.dir = settings.layoutDirection;
    document.documentElement.lang = settings.language === 'ar' ? 'ar' : 'en';
  }, [settings]);

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings(prev => ({ ...prev, ...newSettings }));
  };

  const resetSettings = () => {
    setSettings(defaultSettings);
    localStorage.removeItem('appSettings');
  };

  // Date formatting based on settings
  const formatDate = (date: Date | string): string => {
    const d = typeof date === 'string' ? new Date(date) : date;

    // Apply timezone offset
    const options: Intl.DateTimeFormatOptions = {
      timeZone: settings.timezone,
    };

    const day = d.toLocaleDateString('en-US', { ...options, day: '2-digit' }).padStart(2, '0');
    const month = d.toLocaleDateString('en-US', { ...options, month: '2-digit' }).padStart(2, '0');
    const year = d.toLocaleDateString('en-US', { ...options, year: 'numeric' });

    switch (settings.dateFormat) {
      case 'DD/MM/YYYY':
        return `${day}/${month}/${year}`;
      case 'MM/DD/YYYY':
        return `${month}/${day}/${year}`;
      case 'YYYY-MM-DD':
        return `${year}-${month}-${day}`;
      default:
        return `${day}/${month}/${year}`;
    }
  };

  const formatTime = (date: Date | string): string => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleTimeString('en-US', {
      timeZone: settings.timezone,
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  };

  // Translation function
  const t = useCallback((key: TranslationKey): string => {
    const lang: Language = settings.language === 'ar' ? 'ar' : 'en';
    return translations[lang][key] || translations.en[key] || key;
  }, [settings.language]);

  // RTL check
  const isRTL = settings.layoutDirection === 'rtl' || settings.language === 'ar';

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, resetSettings, formatDate, formatTime, t, isRTL }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}
