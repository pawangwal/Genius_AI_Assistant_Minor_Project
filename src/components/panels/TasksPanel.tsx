import React, { useState, useEffect } from 'react';
import { ListChecks, Plus, Trash2, CheckCircle, Circle, Loader2, AlertCircle } from 'lucide-react';
import { fetchTasks, createTask, updateTask, deleteTask, TaskItem } from '../../services/api';

const TasksPanel: React.FC = () => {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [newTask, setNewTask] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTasks = async () => {
    try {
      setError(null);
      const items = await fetchTasks();
      setTasks(items);
    } catch (err: any) {
      setError(err.message || 'Unable to connect to tasks database.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTask.trim()) return;

    try {
      const created = await createTask(newTask.trim());
      setTasks((prev) => [created, ...prev]);
      setNewTask('');
    } catch (err: any) {
      setError(err.message || 'Failed to create task');
    }
  };

  const handleToggle = async (id: string, currentCompleted: boolean) => {
    try {
      const updated = await updateTask(id, { completed: !currentCompleted });
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
    } catch (err: any) {
      setError(err.message || 'Failed to update task');
    }
  };

  const handleRemove = async (id: string) => {
    try {
      await deleteTask(id);
      setTasks((prev) => prev.filter((t) => t.id !== id));
    } catch (err: any) {
      setError(err.message || 'Failed to delete task');
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-6 border-b border-cyan-900/40 pb-3">
        <div className="flex items-center">
          <ListChecks className="text-cyan-400 mr-2" size={24} />
          <div>
            <h2 className="text-xl font-bold text-cyan-300">Persistent Tasks</h2>
            <p className="text-xs text-cyan-600">PostgreSQL-backed async task store</p>
          </div>
        </div>
        {loading && <Loader2 className="animate-spin text-cyan-400" size={18} />}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-950/50 border border-red-800 rounded-lg text-red-300 text-xs flex items-center gap-2">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={newTask}
            onChange={(e) => setNewTask(e.target.value)}
            placeholder="Add a new task..."
            className="flex-1 bg-black/40 border border-cyan-900/60 rounded-lg px-4 py-2 text-white placeholder-cyan-700 focus:outline-none focus:border-cyan-500 text-sm"
          />
          <button
            type="submit"
            className="bg-cyan-900/60 hover:bg-cyan-800/80 text-cyan-300 px-4 rounded-lg flex items-center transition-colors"
          >
            <Plus size={18} />
          </button>
        </div>
      </form>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {tasks.length === 0 && !loading && (
          <div className="text-center py-10 text-cyan-700 text-sm">
            No active tasks. Create one above or speak to Genius!
          </div>
        )}
        {tasks.map((task) => (
          <div
            key={task.id}
            className="flex items-center gap-3 p-3 bg-black/30 border border-cyan-900/40 rounded-lg group hover:border-cyan-700/50 transition-all"
          >
            <button
              onClick={() => handleToggle(task.id, task.completed)}
              className="text-cyan-400 hover:text-cyan-300"
            >
              {task.completed ? (
                <CheckCircle size={18} className="text-emerald-400" />
              ) : (
                <Circle size={18} />
              )}
            </button>

            <span className={`flex-1 text-sm ${task.completed ? 'line-through text-cyan-700' : 'text-cyan-200'}`}>
              {task.title}
            </span>

            <button
              onClick={() => handleRemove(task.id)}
              className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 transition-opacity"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TasksPanel;