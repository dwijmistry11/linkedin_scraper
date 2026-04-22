import type { Company } from '../../types';
import Section from './Section';
import Field from './Field';

export default function CompanyCard({ data }: { data: Company }) {
  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
        <h3 className="text-xl font-semibold">{data.name || 'Unknown Company'}</h3>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <Field label="Industry" value={data.industry} />
          <Field label="Company Size" value={data.company_size} />
          <Field label="Headquarters" value={data.headquarters} />
          <Field label="Founded" value={data.founded} />
          <Field label="Type" value={data.company_type} />
          <Field label="Website" value={data.website} />
          <Field label="Phone" value={data.phone} />
          <Field label="Headcount" value={data.headcount} />
          <Field label="Specialties" value={data.specialties} />
        </dl>
        {data.about_us && (
          <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">{data.about_us}</p>
        )}
      </div>

      {data.employees.length > 0 && (
        <Section title="Employees" count={data.employees.length}>
          <div className="space-y-1">
            {data.employees.map((e, i) => (
              <div key={i} className="text-sm">
                <span className="font-medium">{e.name}</span>
                {e.designation && (
                  <span className="text-gray-500 dark:text-gray-400"> - {e.designation}</span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
