import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Building2, Users, UserCheck, Plus } from 'lucide-react';
import { listCompanies } from '../api/companies';
import type { CRMCompany } from '../types';
import { getLinkedInUrl } from '../types';

export default function DashboardPage() {
  const [companies, setCompanies] = useState<CRMCompany[]>([]);

  useEffect(() => {
    listCompanies().then(({ data }) => setCompanies(data.companies || [])).catch(() => {});
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 text-center">
          <Building2 size={28} className="mx-auto mb-2 text-blue-500" />
          <p className="text-3xl font-bold">{companies.length}</p>
          <p className="text-xs text-gray-500 mt-1">Companies</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 text-center">
          <Users size={28} className="mx-auto mb-2 text-green-500" />
          <p className="text-3xl font-bold">-</p>
          <p className="text-xs text-gray-500 mt-1">Users Discovered</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 text-center">
          <UserCheck size={28} className="mx-auto mb-2 text-purple-500" />
          <p className="text-3xl font-bold">-</p>
          <p className="text-xs text-gray-500 mt-1">Profiles Scraped</p>
        </div>
      </div>

      {/* Quick action */}
      <Link
        to="/companies"
        className="block bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800 hover:border-blue-400 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Plus size={20} className="text-blue-600" />
          <div>
            <p className="font-medium text-blue-700 dark:text-blue-300">Add & Scrape Companies</p>
            <p className="text-xs text-blue-500 dark:text-blue-400">Monitor LinkedIn companies, extract engaged users, scrape profiles</p>
          </div>
        </div>
      </Link>

      {/* Recent companies */}
      <div>
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Monitored Companies</h3>
        {companies.length === 0 ? (
          <p className="text-sm text-gray-400">No companies yet. Add one to start.</p>
        ) : (
          <div className="space-y-2">
            {companies.slice(0, 10).map((c) => (
              <Link
                key={c.id}
                to={`/companies/${c.id}`}
                className="block bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 hover:border-blue-300 transition-colors"
              >
                <p className="font-medium text-sm">{c.name || 'Unnamed'}</p>
                <p className="text-xs text-gray-400 truncate">{getLinkedInUrl(c.linkedinUrl)}</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
