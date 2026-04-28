import { useEffect, useState } from 'react';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import api from '../api/client';
import * as crmApi from '../api/crm';
import type { AppSettings } from '../types';

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [health, setHealth] = useState<{ status: string; version: string; active_browsers: number } | null>(null);

  // CRM state
  const [crm, setCrm] = useState<crmApi.CRMSettings | null>(null);
  const [crmUrl, setCrmUrl] = useState('');
  const [crmApiKey, setCrmApiKey] = useState('');
  const [crmAutoSync, setCrmAutoSync] = useState(false);
  const [crmSaving, setCrmSaving] = useState(false);
  const [crmStatus, setCrmStatus] = useState<boolean | null>(null);
  const [crmTesting, setCrmTesting] = useState(false);
  const [syncingAll, setSyncingAll] = useState(false);
  const [syncAllResult, setSyncAllResult] = useState<string | null>(null);

  useEffect(() => {
    api.get<AppSettings>('/settings').then(({ data }) => setSettings(data));
    api.get('/health').then(({ data }) => setHealth(data));
    crmApi.getCRMSettings().then(({ data }) => {
      setCrm(data);
      setCrmUrl(data.url);
      setCrmAutoSync(data.auto_sync);
    });
  }, []);

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const { data } = await api.put<AppSettings>('/settings', settings);
      setSettings(data);
    } catch (e) {
      alert('Failed to save settings');
    }
    setSaving(false);
  };

  const saveCRM = async () => {
    setCrmSaving(true);
    try {
      const payload: any = { url: crmUrl, auto_sync: crmAutoSync };
      if (crmApiKey) payload.api_key = crmApiKey;
      const { data } = await crmApi.updateCRMSettings(payload);
      setCrm(data);
      setCrmApiKey('');
      setCrmStatus(null);
    } catch (e) {
      alert('Failed to save CRM settings');
    }
    setCrmSaving(false);
  };

  const testConnection = async () => {
    setCrmTesting(true);
    setCrmStatus(null);
    try {
      const { data } = await crmApi.getCRMStatus();
      setCrmStatus(data.connected);
    } catch {
      setCrmStatus(false);
    }
    setCrmTesting(false);
  };

  const handleSyncAll = async () => {
    setSyncingAll(true);
    setSyncAllResult(null);
    try {
      const { data } = await crmApi.syncAllToCRM();
      const d = data.detail;
      setSyncAllResult(`Synced: ${d.synced ?? 0}, Failed: ${d.failed ?? 0}`);
    } catch (e: any) {
      setSyncAllResult(e.response?.data?.detail || 'Sync failed');
    }
    setSyncingAll(false);
  };

  if (!settings) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-2xl font-bold">Settings</h2>

      {health && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">System Status</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-gray-400">Status</p>
              <p className="font-medium text-green-600">{health.status}</p>
            </div>
            <div>
              <p className="text-gray-400">Version</p>
              <p className="font-medium">{health.version}</p>
            </div>
            <div>
              <p className="text-gray-400">Active Browsers</p>
              <p className="font-medium">{health.active_browsers}</p>
            </div>
          </div>
        </div>
      )}

      {/* Browser Settings */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-4">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Browser Settings</h3>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Headless Mode</p>
            <p className="text-xs text-gray-400">Run browser without visible window (may not work with LinkedIn)</p>
          </div>
          <button
            onClick={() => setSettings({ ...settings, browser_headless: !settings.browser_headless })}
            className={`w-10 h-6 rounded-full transition-colors ${settings.browser_headless ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`}
          >
            <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${settings.browser_headless ? 'translate-x-4' : ''}`} />
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Slow Mo (ms)</label>
          <input type="number" value={settings.browser_slow_mo} onChange={(e) => setSettings({ ...settings, browser_slow_mo: Number(e.target.value) })} min={0} className="w-32 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Max Concurrent Sessions</label>
          <input type="number" value={settings.max_concurrent_sessions} onChange={(e) => setSettings({ ...settings, max_concurrent_sessions: Number(e.target.value) })} min={1} max={10} className="w-32 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        <button onClick={save} disabled={saving} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2">
          {saving && <Loader2 size={14} className="animate-spin" />}
          Save Settings
        </button>
      </div>

      {/* CRM Integration */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-4">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Twenty CRM Integration</h3>

        <div>
          <label className="block text-sm font-medium mb-1">CRM URL</label>
          <input
            type="url"
            value={crmUrl}
            onChange={(e) => setCrmUrl(e.target.value)}
            placeholder="https://crm.yourdomain.com"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            API Key {crm?.has_api_key && <span className="text-xs text-green-500 font-normal ml-1">(configured)</span>}
          </label>
          <input
            type="password"
            value={crmApiKey}
            onChange={(e) => setCrmApiKey(e.target.value)}
            placeholder={crm?.has_api_key ? 'Leave blank to keep current key' : 'Paste your Twenty API key'}
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none font-mono text-xs"
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Auto-sync</p>
            <p className="text-xs text-gray-400">Automatically push results to CRM after scraping completes</p>
          </div>
          <button
            onClick={() => setCrmAutoSync(!crmAutoSync)}
            className={`w-10 h-6 rounded-full transition-colors ${crmAutoSync ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`}
          >
            <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${crmAutoSync ? 'translate-x-4' : ''}`} />
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={saveCRM} disabled={crmSaving} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2">
            {crmSaving && <Loader2 size={14} className="animate-spin" />}
            Save CRM Settings
          </button>
          <button onClick={testConnection} disabled={crmTesting} className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm rounded-lg flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800">
            {crmTesting && <Loader2 size={14} className="animate-spin" />}
            Test Connection
          </button>
          {crmStatus === true && <CheckCircle size={18} className="text-green-500" />}
          {crmStatus === false && <XCircle size={18} className="text-red-500" />}
        </div>

        {crm?.has_api_key && (
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
            <div className="flex items-center gap-3">
              <button onClick={handleSyncAll} disabled={syncingAll} className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm rounded-lg flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800">
                {syncingAll && <Loader2 size={14} className="animate-spin" />}
                Sync All Unsynced Results
              </button>
              {syncAllResult && <span className="text-sm text-gray-500">{syncAllResult}</span>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
