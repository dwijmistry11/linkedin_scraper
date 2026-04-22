import type { Post } from '../../types';

export default function PostCard({ data }: { data: Post }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-2">
      {data.posted_date && (
        <p className="text-xs text-gray-400">{data.posted_date}</p>
      )}
      {data.text && (
        <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap line-clamp-6">
          {data.text}
        </p>
      )}
      <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
        {data.reactions_count != null && <span>{data.reactions_count} reactions</span>}
        {data.comments_count != null && <span>{data.comments_count} comments</span>}
        {data.reposts_count != null && <span>{data.reposts_count} reposts</span>}
      </div>
      {data.linkedin_url && (
        <a
          href={data.linkedin_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          View on LinkedIn
        </a>
      )}
    </div>
  );
}
