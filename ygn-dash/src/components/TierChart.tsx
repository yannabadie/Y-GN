import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface TierChartProps {
  hot: number;
  warm: number;
  cold: number;
}

const COLORS = ["#ef4444", "#f59e0b", "#3b82f6"];

export function TierChart({ hot, warm, cold }: TierChartProps) {
  const data = [
    { name: "Hot", value: hot },
    { name: "Warm", value: warm },
    { name: "Cold", value: cold },
  ];

  const total = hot + warm + cold;
  if (total === 0) {
    return <p className="text-gray-500 text-sm">No memory entries.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          dataKey="value"
          label={({ name, value }) => `${name}: ${value}`}
        >
          {data.map((_, index) => (
            <Cell key={index} fill={COLORS[index]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
