interface Props {
  label: string;
  value: string | number | null | undefined;
}

export default function Field({ label, value }: Props) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="py-1">
      <dt className="text-xs text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className="text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap">{value}</dd>
    </div>
  );
}
