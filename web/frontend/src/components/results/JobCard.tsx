import type { Job } from '../../types';
import Field from './Field';

export default function JobCard({ data }: { data: Job }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 space-y-2">
      <h3 className="text-xl font-semibold">{data.job_title || 'Unknown Position'}</h3>
      <dl className="grid grid-cols-2 gap-2">
        <Field label="Company" value={data.company} />
        <Field label="Location" value={data.location} />
        <Field label="Posted" value={data.posted_date} />
        <Field label="Applicants" value={data.applicant_count} />
        <Field label="Benefits" value={data.benefits} />
      </dl>
      {data.job_description && (
        <div className="mt-3">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Description</p>
          <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
            {data.job_description}
          </p>
        </div>
      )}
    </div>
  );
}
