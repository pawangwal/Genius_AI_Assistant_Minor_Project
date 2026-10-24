/**
 * Typed client for Genius AI Assistant Backend API v1
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export interface IPLPredictionRequest {
  batting_team: string;
  bowling_team: string;
  city: string;
  target_score: number;
  current_score: number;
  overs_completed: number;
  balls_in_over: number;
  wickets_out: number;
}

export interface DerivedMatchFeatures {
  legal_balls_bowled: number;
  balls_left: number;
  runs_left: number;
  wickets_left: number;
  crr: number;
  rrr: number;
  total_runs_x: number;
}

export interface IPLPredictionResponse {
  batting_team: string;
  bowling_team: string;
  city: string;
  batting_win_probability: number;
  bowling_win_probability: number;
  projected_winner: string;
  match_completed: boolean;
  status_summary: string;
  derived_features: DerivedMatchFeatures;
  inference_latency_ms: number;
}

export interface TaskItem {
  id: string;
  title: string;
  completed: boolean;
  category: string;
  user_id?: string;
  created_at: string;
}

export interface ReminderItem {
  id: string;
  title: string;
  due_time: string;
  completed: boolean;
  user_id?: string;
  created_at: string;
}

export interface HealthCheckResponse {
  status: 'ready' | 'unready' | 'alive';
  dependencies?: {
    database: string;
    ipl_model: string;
  };
}

export async function checkBackendHealth(): Promise<HealthCheckResponse> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/health/ready`);
  return await resp.json();
}

export async function predictIPLWin(req: IPLPredictionRequest): Promise<IPLPredictionResponse> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/predictions/ipl`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({ detail: 'Failed to predict IPL match' }));
    throw new Error(errorData.detail || `Prediction failed with status ${resp.status}`);
  }

  return await resp.json();
}

export async function fetchTasks(): Promise<TaskItem[]> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/tasks`);
  if (!resp.ok) throw new Error('Failed to fetch tasks');
  return await resp.json();
}

export async function createTask(title: string, category: string = 'general'): Promise<TaskItem> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, category }),
  });
  if (!resp.ok) throw new Error('Failed to create task');
  return await resp.json();
}

export async function updateTask(id: string, updates: { completed?: boolean; title?: string }): Promise<TaskItem> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) throw new Error('Failed to update task');
  return await resp.json();
}

export async function deleteTask(id: string): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/tasks/${id}`, {
    method: 'DELETE',
  });
  if (!resp.ok) throw new Error('Failed to delete task');
}

export async function fetchReminders(): Promise<ReminderItem[]> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/reminders`);
  if (!resp.ok) throw new Error('Failed to fetch reminders');
  return await resp.json();
}

export async function createReminder(title: string, due_time: string): Promise<ReminderItem> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/reminders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, due_time }),
  });
  if (!resp.ok) throw new Error('Failed to create reminder');
  return await resp.json();
}

export async function deleteReminder(id: string): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/v1/reminders/${id}`, {
    method: 'DELETE',
  });
  if (!resp.ok) throw new Error('Failed to delete reminder');
}
