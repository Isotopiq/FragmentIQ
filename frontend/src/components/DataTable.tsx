export function DataTable({
  rows,
  columns: selectedColumns,
  maxRows = 25,
  maxColumns = 14,
  title,
  empty = "No rows available yet.",
}: {
  rows: Record<string, unknown>[];
  columns?: string[];
  maxRows?: number;
  maxColumns?: number;
  title?: string;
  empty?: string;
}) {
  const columns = (selectedColumns ?? Array.from(new Set(rows.flatMap((row) => Object.keys(row))))).slice(0, maxColumns);
  if (!rows.length) {
    return <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">{empty}</div>;
  }
  return (
    <div>
      {title && <h3 className="mb-3 text-lg font-semibold text-slate-900 dark:text-white">{title}</h3>}
      <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
          <thead className="bg-slate-50 dark:bg-slate-800">
            <tr>
              {columns.map((column) => (
                <th key={column} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
            {rows.slice(0, maxRows).map((row, idx) => (
              <tr key={idx}>
                {columns.map((column) => (
                  <td key={column} className="whitespace-nowrap px-3 py-2 text-xs text-slate-700 dark:text-slate-200">
                    {String(row[column] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
