import clsx from "clsx";

const colors: Record<string, string> = {
  Low: "bg-green-100 text-green-800",
  Medium: "bg-yellow-100 text-yellow-800",
  High: "bg-orange-100 text-orange-800",
  Critical: "bg-red-100 text-red-800",
};

export default function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="text-gray-400">—</span>;
  return (
    <span className={clsx("px-2 py-0.5 rounded-full text-xs font-medium", colors[priority] ?? "bg-gray-100 text-gray-700")}>
      {priority}
    </span>
  );
}
