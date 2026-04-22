interface Props {
  percent: number;
  message: string;
  error: string | null;
  completed: boolean;
}

export default function ProgressPanel({ percent, message, error, completed }: Props) {
  if (error) {
    return (
      <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <p className="text-sm font-medium text-red-700 dark:text-red-400">Scraping failed</p>
        <p className="text-sm text-red-600 dark:text-red-300 mt-1">{error}</p>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
        <p className="text-sm font-medium text-green-700 dark:text-green-400">Scraping completed!</p>
      </div>
    );
  }

  if (percent === 0 && !message) return null;

  return (
    <div className="mt-4 space-y-2">
      <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
        <span>{message || 'Starting...'}</span>
        <span>{percent}%</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
        <div
          className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
