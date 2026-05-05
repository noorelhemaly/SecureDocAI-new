import { useState } from 'react';
import { Save, Globe, Check, RotateCcw } from 'lucide-react';
import { useSettings } from '../context/SettingsContext';

export function SettingsView() {
  const { settings, updateSettings, resetSettings, t, isRTL } = useSettings();
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved'>('idle');

  const handleSave = () => {
    setSaveStatus('saved');
    setTimeout(() => setSaveStatus('idle'), 2000);
  };

  const handleReset = () => {
    if (window.confirm('Reset all settings to defaults? This cannot be undone.')) {
      resetSettings();
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    }
  };

  return (
    <div className={`p-6 max-w-5xl mx-auto ${isRTL ? 'rtl' : 'ltr'}`} dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">{t('settings.title')}</h2>
        <p className="text-gray-600 dark:text-gray-400 mt-1">
          {t('settings.subtitle')}
        </p>
      </div>

      <div className="space-y-6">
        {/* General Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Globe className="w-5 h-5 text-[#1E3A8A]" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('settings.generalSettings')}</h3>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.language')} / اللغة
                </label>
                <select
                  value={settings.language}
                  onChange={(e) => updateSettings({ language: e.target.value as 'en' | 'ar' | 'both' })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="en">English</option>
                  <option value="ar">العربية (Arabic)</option>
                  <option value="both">English / العربية</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.layoutDirection')}
                </label>
                <select
                  value={settings.layoutDirection}
                  onChange={(e) => updateSettings({ layoutDirection: e.target.value as 'ltr' | 'rtl' })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="ltr">{t('settings.ltr')}</option>
                  <option value="rtl">{t('settings.rtl')}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.timezone')}
                </label>
                <select
                  value={settings.timezone}
                  onChange={(e) => updateSettings({ timezone: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="Africa/Cairo">Africa/Cairo (GMT+2)</option>
                  <option value="UTC">UTC (GMT+0)</option>
                  <option value="Europe/London">Europe/London (GMT+0/+1)</option>
                  <option value="Asia/Dubai">Asia/Dubai (GMT+4)</option>
                  <option value="Asia/Riyadh">Asia/Riyadh (GMT+3)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.dateFormat')}
                </label>
                <select
                  value={settings.dateFormat}
                  onChange={(e) => updateSettings({ dateFormat: e.target.value as 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD' })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="DD/MM/YYYY">DD/MM/YYYY (31/01/2025)</option>
                  <option value="MM/DD/YYYY">MM/DD/YYYY (01/31/2025)</option>
                  <option value="YYYY-MM-DD">YYYY-MM-DD (2025-01-31)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className={`flex gap-3 ${isRTL ? 'justify-start' : 'justify-end'}`}>
          <button
            onClick={handleReset}
            className="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-all font-medium flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            {t('settings.resetDefaults')}
          </button>
          <button
            onClick={handleSave}
            className="px-6 py-3 bg-gradient-to-r from-[#1E3A8A] to-[#0891B2] text-white rounded-lg hover:opacity-90 transition-all font-medium shadow-lg flex items-center gap-2"
          >
            {saveStatus === 'saved' ? (
              <>
                <Check className="w-4 h-4" />
                {t('settings.saved')}
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                {t('settings.saveSettings')}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
