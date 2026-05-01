import { Table } from "flowbite-react";

export function DataTable({ rows, maxRows = 25 }: { rows: Record<string, unknown>[]; maxRows?: number }) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 14);
  if (!rows.length) {
    return <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-slate-500">No rows available yet.</div>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <Table hoverable>
        <Table.Head>
          {columns.map((column) => (
            <Table.HeadCell key={column}>{column}</Table.HeadCell>
          ))}
        </Table.Head>
        <Table.Body className="divide-y">
          {rows.slice(0, maxRows).map((row, idx) => (
            <Table.Row key={idx} className="bg-white">
              {columns.map((column) => (
                <Table.Cell key={column} className="whitespace-nowrap text-xs">
                  {String(row[column] ?? "")}
                </Table.Cell>
              ))}
            </Table.Row>
          ))}
        </Table.Body>
      </Table>
    </div>
  );
}
