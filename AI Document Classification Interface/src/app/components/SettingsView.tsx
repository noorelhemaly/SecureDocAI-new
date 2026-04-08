import { useState } from 'react';
import { Save, Bell, Shield, Globe, Database, Lock, AlertTriangle, Check, RotateCcw, Fingerprint } from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import { updateBackendSettings } from '../services/api';

export function SettingsView() {
  const { settings, updateSettings, resetSettings, t, isRTL } = useSettings();
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved'>('idle');

  const handleSave = async () => {
    // Settings are auto-saved via context, but also sync to backend
    try {
      await updateBackendSettings({
        confidenceThreshold: settings.confidenceThreshold,
        hybridMode: settings.hybridMode,
        autoEscalate: settings.autoEscalate,
        autoEncryptC2C3: settings.autoEncryptC2C3,
        enableBlockchainProtection: settings.enableBlockchainProtection,
        enableDigitalSignature: settings.enableDigitalSignature,
      });
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to sync settings to backend:', error);
      // Still show saved for local storage
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    }
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

        {/* Classification Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-[#1E3A8A]" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('settings.classificationParams')}</h3>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('settings.confidenceThreshold')} ({settings.confidenceThreshold}%)
              </label>
              <input
                type="range"
                min="50"
                max="100"
                value={settings.confidenceThreshold}
                onChange={(e) => updateSettings({ confidenceThreshold: parseInt(e.target.value) })}
                className="w-full accent-[#1E3A8A]"
              />
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                <span>50% ({t('settings.morePermissive')})</span>
                <span className="text-[#1E3A8A] font-medium">{settings.confidenceThreshold}%</span>
                <span>100% ({t('settings.moreStrict')})</span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.llmModel')}
                </label>
                <div className="w-full px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-blue-700 dark:text-blue-400 flex items-center gap-2">
                  <span className="text-lg">🦙</span>
                  <span className="font-medium">LLaMA 3 (via Ollama)</span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {t('settings.runningLocally')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.hybridMode')}
                </label>
                <select
                  value={settings.hybridMode}
                  onChange={(e) => updateSettings({ hybridMode: e.target.value as 'conservative' | 'balanced' | 'aggressive' })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                >
                  <option value="conservative">{t('settings.conservative')}</option>
                  <option value="balanced">{t('settings.balanced')}</option>
                  <option value="aggressive">{t('settings.aggressive')}</option>
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t('settings.classificationOptions')}
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.autoEscalate}
                  onChange={(e) => updateSettings({ autoEscalate: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.autoEscalate')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.requireC3Review}
                  onChange={(e) => updateSettings({ requireC3Review: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.requireC3Review')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.realtimeNotifications}
                  onChange={(e) => updateSettings({ realtimeNotifications: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.realtimeNotifications')}
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Security Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Lock className="w-5 h-5 text-[#1E3A8A]" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('settings.securityEncryption')}</h3>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.encryptionAlgorithm')}
                </label>
                <div className="w-full px-3 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-400 flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  <span className="font-medium">Kyber-768 + AES-256-GCM</span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {t('settings.pqcQuantumResistant')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('settings.sessionTimeout')}
                </label>
                <input
                  type="number"
                  min="5"
                  max="120"
                  value={settings.sessionTimeout}
                  onChange={(e) => updateSettings({ sessionTimeout: parseInt(e.target.value) || 30 })}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t('settings.securityPolicies')}
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.require2FA}
                  onChange={(e) => updateSettings({ require2FA: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.require2FA')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.autoEncryptC2C3}
                  onChange={(e) => updateSettings({ autoEncryptC2C3: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.autoEncryptC2C3')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.auditLogging}
                  onChange={(e) => updateSettings({ auditLogging: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.auditLogging')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.restrictC3Downloads}
                  onChange={(e) => updateSettings({ restrictC3Downloads: e.target.checked })}
                  className="w-4 h-4 text-[#1E3A8A] rounded"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {t('settings.restrictC3Downloads')}
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Integrity Protection Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Fingerprint className="w-5 h-5 text-[#1E3A8A]" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('settings.integrityProtection')}</h3>
          </div>

          <div className="space-y-2">
            <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('settings.enableBlockchainProtection')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.enableBlockchainProtectionDesc')}
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.enableBlockchainProtection}
                onChange={(e) => updateSettings({ enableBlockchainProtection: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
            </label>

            <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('settings.enableDigitalSignature')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.enableDigitalSignatureDesc')}
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.enableDigitalSignature}
                onChange={(e) => updateSettings({ enableDigitalSignature: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
            </label>
          </div>
        </div>

        {/* Notification Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Bell className="w-5 h-5 text-[#1E3A8A]" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('settings.notifications')}</h3>
          </div>

          <div className="space-y-2">
            <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('settings.classificationComplete')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.classificationCompleteDesc')}
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.notifyClassificationComplete}
                onChange={(e) => updateSettings({ notifyClassificationComplete: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
            </label>

            <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('settings.highRiskDetection')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.highRiskDetectionDesc')}
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.notifyHighRisk}
                onChange={(e) => updateSettings({ notifyHighRisk: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
            </label>

            <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('settings.classificationDisagreement')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.classificationDisagreementDesc')}
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.notifyDisagreement}
                onChange={(e) => updateSettings({ notifyDisagreement: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
            </label>

            <label className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {t('settings.systemUpdates')}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.systemUpdatesDesc')}
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.notifySystemUpdates}
                onChange={(e) => updateSettings({ notifySystemUpdates: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
            </label>
          </div>
        </div>

        {/* Compliance Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-[#1E3A8A]" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t('settings.pdapCompliance')}
            </h3>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 mb-4 border border-blue-200 dark:border-blue-800">
            <div className={`flex items-start gap-3 ${isRTL ? 'flex-row-reverse' : ''}`}>
              <AlertTriangle className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-blue-900 dark:text-blue-300 font-medium">
                  {t('settings.pdapTitle')}
                </p>
                <p className="text-xs text-blue-800 dark:text-blue-400 mt-1">
                  {t('settings.pdapDesc')}
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked disabled className="w-4 h-4 text-[#1E3A8A] rounded opacity-60" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {t('settings.mandatoryAudit')}
              </span>
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked disabled className="w-4 h-4 text-[#1E3A8A] rounded opacity-60" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {t('settings.dataRetention')}
              </span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.generateComplianceReports}
                onChange={(e) => updateSettings({ generateComplianceReports: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {t('settings.complianceReports')}
              </span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enableDSARWorkflow}
                onChange={(e) => updateSettings({ enableDSARWorkflow: e.target.checked })}
                className="w-4 h-4 text-[#1E3A8A] rounded"
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {t('settings.dsarWorkflow')}
              </span>
            </label>
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
