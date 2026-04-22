import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import api from '../api/client';
import type { AppSettings } from '../types';

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [health, setHealth] = useState<{ status: string; version: string; active_browsers: number } | null>(null);

  useEffect(() => {
    api.get<AppSettings>('/settings').then(({ data }) => setSettings(data));
    api.get('/health').then(({ data }) => setHealth(data));
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

      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-4">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Browser Settings</h3>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Headless Mode</p>
            <p className="text-xs text-gray-400">Run browser without visible window (may not work with LinkedIn)</p>
          </div>
          <button
            onClick={() => setSettings({ ...settings, browser_headless: !settings.browser_headless })}
            className={`w-10 h-6 rounded-full transition-colors ${
              settings.browser_headless ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
            }`}
          >
            <div
              className={`w-4 h-4 bg-white rounded-full transition-transform mx-1 ${
                settings.browser_headless ? 'translate-x-4' : ''
              }`}
            />
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Slow Mo (ms)</label>
          <input
            type="number"
            value={settings.browser_slow_mo}
            onChange={(e) => setSettings({ ...settings, browser_slow_mo: Number(e.target.value) })}
            min={0}
            className="w-32 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
          />
          <p className="text-xs text-gray-400 mt-1">Slow down browser actions for debugging</p>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Max Concurrent Sessions</label>
          <input
            type="number"
            value={settings.max_concurrent_sessions}
            onChange={(e) => setSettings({ ...settings, max_concurrent_sessions: Number(e.target.value) })}
            min={1}
            max={10}
            className="w-32 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
          />
          <p className="text-xs text-gray-400 mt-1">Each session uses ~100-200MB RAM</p>
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          Save Settings
        </button>
      </div>
    </div>
  );
}
