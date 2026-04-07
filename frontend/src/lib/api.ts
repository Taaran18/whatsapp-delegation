import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export const api = axios.create({ baseURL: API_URL });

export interface Task {
  task_id: string;
  timestamp: string | null;
  task_description: string | null;
  assigned_by: string | null;
  assignee_contact: string | null;
  assigned_to: string | null;
  employee_email_id: string | null;
  target_date: string | null;
  priority: "Low" | "Medium" | "High" | "Critical" | null;
  approval_needed: number | null;
  client_name: string | null;
  department: string | null;
  assigned_name: string | null;
  assigned_email_id: string | null;
  comments: string | null;
  source_link: string | null;
  status: "Pending" | "In Progress" | "Completed" | "Cancelled" | null;
  message_type: "text" | "voice" | null;
}

export async function fetchTasks(params?: {
  status?: string;
  priority?: string;
  limit?: number;
  offset?: number;
}): Promise<Task[]> {
  const { data } = await api.get<Task[]>("/tasks/", { params });
  return data;
}

export async function updateTask(
  taskId: string,
  body: Partial<Task>
): Promise<Task> {
  const { data } = await api.patch<Task>(`/tasks/${taskId}`, body);
  return data;
}
