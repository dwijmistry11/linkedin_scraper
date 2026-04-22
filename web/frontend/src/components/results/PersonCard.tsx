import type { Person } from '../../types';
import Section from './Section';
import Field from './Field';

export default function PersonCard({ data }: { data: Person }) {
  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
        <h3 className="text-xl font-semibold">{data.name || 'Unknown'}</h3>
        <div className="mt-2 space-y-1">
          <Field label="Location" value={data.location} />
          <Field label="LinkedIn URL" value={data.linkedin_url} />
          {data.open_to_work && (
            <span className="inline-block mt-1 px-2 py-0.5 text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded">
              Open to work
            </span>
          )}
        </div>
        {data.about && (
          <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">{data.about}</p>
        )}
      </div>

      {data.experiences.length > 0 && (
        <Section title="Experience" count={data.experiences.length} defaultOpen>
          <div className="space-y-3">
            {data.experiences.map((exp, i) => (
              <div key={i} className="border-l-2 border-blue-300 dark:border-blue-700 pl-3">
                <p className="text-sm font-medium">{exp.position_title}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{exp.institution_name}</p>
                <p className="text-xs text-gray-400">
                  {[exp.from_date, exp.to_date].filter(Boolean).join(' - ')}
                  {exp.duration && ` (${exp.duration})`}
                </p>
                {exp.location && <p className="text-xs text-gray-400">{exp.location}</p>}
                {exp.description && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{exp.description}</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.educations.length > 0 && (
        <Section title="Education" count={data.educations.length}>
          <div className="space-y-3">
            {data.educations.map((edu, i) => (
              <div key={i} className="border-l-2 border-green-300 dark:border-green-700 pl-3">
                <p className="text-sm font-medium">{edu.institution_name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{edu.degree}</p>
                <p className="text-xs text-gray-400">
                  {[edu.from_date, edu.to_date].filter(Boolean).join(' - ')}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.accomplishments.length > 0 && (
        <Section title="Accomplishments" count={data.accomplishments.length}>
          <div className="space-y-2">
            {data.accomplishments.map((a, i) => (
              <div key={i}>
                <p className="text-sm font-medium">{a.title}</p>
                <p className="text-xs text-gray-400">
                  {a.category}
                  {a.issuer && ` - ${a.issuer}`}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data.contacts.length > 0 && (
        <Section title="Contacts" count={data.contacts.length}>
          <div className="space-y-1">
            {data.contacts.map((c, i) => (
              <div key={i} className="text-sm">
                <span className="text-gray-500 dark:text-gray-400">{c.type}: </span>
                <span>{c.value}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
