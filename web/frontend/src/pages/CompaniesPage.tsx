import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, Building2, Loader2 } from 'lucide-react';
import { listCompanies, addCompany } from '../api/companies';
import type { CRMCompany } from '../types';
import { getLinkedInUrl } from '../types';

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CRMCompany[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const load = async (q?: string) => {
    setLoading(true);
    try {
      const { data } = await listCompanies(q);
      setCompanies(data.companies || []);
    } catch {
      setCompanies([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => load(search || undefined), 300);
    return () => clearTimeout(timeout);
  }, [search]);

  const handleAdd = async () => {
    if (!newUrl.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      await addCompany(newUrl.trim(), newName.trim() || undefined);
      setNewUrl('');
      setNewName('');
      setShowAdd(false);
      load();
    } catch (e: any) {
      setAddError(e.response?.data?.detail || 'Failed to add company');
    }
    setAdding(false);
  };

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Companies</h2>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={16} /> Add Company
        </button>
      </div>

      {showAdd && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              LinkedIn Company / Showcase URL
            </label>
            <input
              type="url"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder="https://www.linkedin.com/company/microsoft/"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Name (optional)
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Auto-detected from URL if empty"
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          {addError && <p className="text-sm text-red-500">{addError}</p>}
          <div className="flex gap-2">
            <button onClick={handleAdd} disabled={adding || !newUrl.trim()} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded-lg flex items-center gap-2">
              {adding && <Loader2 size={14} className="animate-spin" />} Add
            </button>
            <button onClick={() => setShowAdd(false)} className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-sm rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies..."
          className="w-full pl-9 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 outline-none"
        />
      </div>

      {/* Companies list */}
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="animate-spin text-gray-400" /></div>
      ) : companies.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Building2 size={48} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No companies found. Add one to start scraping.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {companies.map((c) => (
            <Link
              key={c.id}
              to={`/companies/${c.id}`}
              className="block bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{c.name || 'Unnamed'}</p>
                  <p className="text-xs text-gray-400 truncate">{getLinkedInUrl(c.linkedinUrl)}</p>
                </div>
                <div className="text-right text-xs text-gray-400">
                  {c.lastPostScrapedAt && (
                    <p>Last scraped: {new Date(c.lastPostScrapedAt).toLocaleDateString()}</p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
