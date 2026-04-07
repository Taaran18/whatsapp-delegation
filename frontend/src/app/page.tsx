"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchTasks } from "@/lib/api";
import TaskTable from "@/components/TaskTable";
import { useState } from "react";
import { RefreshCw } from "lucide-react";

const STATUS_OPTIONS = ["", "Pending", "In Progress", "Completed", "Cancelled"];
const PRIORITY_OPTIONS = ["", "Low", "Medium", "High", "Critical"];

export default function HomePage() {
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");

  const { data: tasks = [], isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["tasks", status, priority],
    queryFn: () => fetchTasks({
      status: status || undefined,
      priority: priority || undefined,
    }),
    refetchInterval: 30_000, // auto-refresh every 30s
  });

  return (
    <div className="max-w-[1600px] mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">WhatsApp Delegation</h1>
          <p className="text-sm text-gray-500 mt-1">Tasks delegated via WhatsApp — auto-refreshes every 30s</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All Statuses"}</option>
          ))}
        </select>

        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        >
          {PRIORITY_OPTIONS.map((p) => (
            <option key={p} value={p}>{p || "All Priorities"}</option>
          ))}
        </select>

        <span className="ml-auto text-sm text-gray-400 self-center">
          {tasks.length} task{tasks.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-16 text-gray-400">Loading tasks...</div>
      ) : isError ? (
        <div className="text-center py-16 text-red-400">Failed to load tasks. Check API connection.</div>
      ) : (
        <TaskTable tasks={tasks} />
      )}
    </div>
  );
}
