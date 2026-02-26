interface StatusCardProps {
  title: string;
  value: string | number;
  status: "ok" | "warning" | "error";
  subtitle?: string;
}

export function StatusCard({ title, value, status, subtitle }: StatusCardProps) {
  const colors = {
    ok: "bg-green-50 text-green-800 border-green-200",
    warning: "bg-yellow-50 text-yellow-800 border-yellow-200",
    error: "bg-red-50 text-red-800 border-red-200",
  };

  return (
    <div className={`rounded-lg border p-4 ${colors[status]}`}>
      <h3 className="text-sm font-medium opacity-75">{title}</h3>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {subtitle && <p className="mt-1 text-xs opacity-60">{subtitle}</p>}
    </div>
  );
}
