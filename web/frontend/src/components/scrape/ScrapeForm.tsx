import { useState } from 'react';
import { Loader2 } from 'lucide-react';

interface Props {
  label: string;
  placeholder: string;
  onSubmit: (url: string) => void;
  loading: boolean;
}

export default function ScrapeForm({ label, placeholder, onSubmit, loading }: Props) {
  const [url, setUrl] = useState('');

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (url.trim()) onSubmit(url.trim());
      }}
      className="space-y-3"
    >
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={placeholder}
          required
          className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center gap-2 transition-colors"
        >
          {loading && <Loader2 size={16} className="animate-spin" />}
          Scrape
        </button>
      </div>
    </form>
  );
}
