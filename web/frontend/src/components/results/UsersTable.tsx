import type { ExtractUsersResult } from '../../types';

export default function UsersTable({ data }: { data: ExtractUsersResult }) {
  const reactions = data.users.filter((u) => u.engagement_type === 'reaction');
  const reposts = data.users.filter((u) => u.engagement_type === 'repost');

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 text-center">
          <p className="text-2xl font-bold text-blue-600">{data.posts_scraped}</p>
          <p className="text-xs text-gray-500">Posts Scraped</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 text-center">
          <p className="text-2xl font-bold text-green-600">{reactions.length}</p>
          <p className="text-xs text-gray-500">Reactors</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 text-center">
          <p className="text-2xl font-bold text-purple-600">{reposts.length}</p>
          <p className="text-xs text-gray-500">Reposters</p>
        </div>
      </div>

      {/* Users table */}
      {data.users.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">No users found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-gray-500 dark:text-gray-400">
                <th className="pb-2 font-medium">#</th>
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Headline</th>
                <th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {data.users.map((user, i) => (
                <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="py-2 text-gray-400">{i + 1}</td>
                  <td className="py-2 font-medium">{user.name}</td>
                  <td className="py-2 text-gray-500 dark:text-gray-400 max-w-xs truncate">
                    {user.headline || '-'}
                  </td>
                  <td className="py-2">
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        user.engagement_type === 'reaction'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                      }`}
                    >
                      {user.engagement_type}
                    </span>
                  </td>
                  <td className="py-2">
                    {user.profile_url ? (
                      <a
                        href={user.profile_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 dark:text-blue-400 hover:underline text-xs"
                      >
                        View
                      </a>
                    ) : (
                      <span className="text-gray-400 text-xs">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
