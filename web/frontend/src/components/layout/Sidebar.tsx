import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  User,
  Building2,
  Briefcase,
  FileText,
  Users,
  History,
  KeyRound,
  Settings,
} from 'lucide-react';

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { heading: 'Scrape' },
  { to: '/scrape/person', label: 'Person', icon: User },
  { to: '/scrape/company', label: 'Company', icon: Building2 },
  { to: '/scrape/job', label: 'Job', icon: Briefcase },
  { to: '/scrape/posts', label: 'Posts', icon: FileText },
  { to: '/scrape/extract-users', label: 'Extract Users', icon: Users },
  { heading: 'Manage' },
  { to: '/history', label: 'History', icon: History },
  { to: '/sessions', label: 'Sessions', icon: KeyRound },
  { to: '/settings', label: 'Settings', icon: Settings },
] as const;

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <aside className="w-56 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 h-full overflow-y-auto">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">LinkedIn Scraper</h1>
      </div>
      <nav className="p-2 space-y-1">
        {nav.map((item, i) => {
          if ('heading' in item) {
            return (
              <p key={i} className="px-3 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-400">
                {item.heading}
              </p>
            );
          }
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`
              }
            >
              <Icon size={18} />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
