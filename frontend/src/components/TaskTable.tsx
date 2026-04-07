"use client";

import { Task } from "@/lib/api";
import PriorityBadge from "./PriorityBadge";
import StatusBadge from "./StatusBadge";
import { Mic, MessageSquare, ExternalLink } from "lucide-react";

const COLUMNS = [
  "Timestamp",
  "Task ID",
  "Task Description",
  "Assigned By",
  "Assignee Contact",
  "Assigned To",
  "Employee Email ID",
  "Target Date",
  "Priority",
  "Approval Needed",
  "Client Name",
  "Department",
  "Assigned Name",
  "Assigned Email ID",
  "Comments",
  "Source Link",
  "Status",
];

function Cell({ children }: { children: React.ReactNode }) {
  return (
    <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-700 border-b border-gray-100 max-w-[200px] truncate">
      {children ?? <span className="text-gray-300">—</span>}
    </td>
  );
}

export default function TaskTable({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        No tasks yet. Send a WhatsApp message starting with <code className="bg-gray-100 px-1 rounded">/task</code> or a voice note.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full bg-white text-left">
        <thead className="bg-gray-50 sticky top-0 z-10">
          <tr>
            {COLUMNS.map((col) => (
              <th key={col} className="px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-200 whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.task_id} className="hover:bg-gray-50 transition-colors">
              <Cell>{task.timestamp ? new Date(task.timestamp).toLocaleString() : null}</Cell>
              <Cell>
                <span className="font-mono font-medium text-indigo-700">{task.task_id}</span>
              </Cell>
              <Cell>
                <span title={task.task_description ?? ""}>{task.task_description}</span>
              </Cell>
              <Cell>{task.assigned_by}</Cell>
              <Cell>{task.assignee_contact}</Cell>
              <Cell>{task.assigned_to}</Cell>
              <Cell>{task.employee_email_id}</Cell>
              <Cell>{task.target_date}</Cell>
              <Cell><PriorityBadge priority={task.priority} /></Cell>
              <Cell>{task.approval_needed ? "Yes" : "No"}</Cell>
              <Cell>{task.client_name}</Cell>
              <Cell>{task.department}</Cell>
              <Cell>{task.assigned_name}</Cell>
              <Cell>{task.assigned_email_id}</Cell>
              <Cell>
                <span title={task.comments ?? ""}>{task.comments}</span>
              </Cell>
              <Cell>
                {task.source_link ? (
                  <a href={task.source_link} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1 text-indigo-600 hover:underline">
                    {task.message_type === "voice" ? <Mic size={12} /> : <MessageSquare size={12} />}
                    <ExternalLink size={12} />
                    Open
                  </a>
                ) : (
                  task.message_type === "voice" ? <Mic size={14} className="text-gray-400" /> : null
                )}
              </Cell>
              <Cell><StatusBadge status={task.status} /></Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
