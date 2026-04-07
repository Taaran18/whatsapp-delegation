import clsx from "clsx";

const colors: Record<string, string> = {
  Pending: "bg-gray-100 text-gray-700",
  "In Progress": "bg-blue-100 text-blue-800",
  Completed: "bg-green-100 text-green-800",
  Cancelled: "bg-red-100 text-red-700",
};

export default function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-gray-400">—</span>;
  return (
    <span className={clsx("px-2 py-0.5 rounded-full text-xs font-medium", colors[status] ?? "bg-gray-100 text-gray-700")}>
      {status}
    </span>
  );
}
