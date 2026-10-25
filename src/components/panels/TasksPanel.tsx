import React, { useState, useEffect } from 'react';
import { ListChecks, Plus, Trash2, CheckCircle, Circle, Loader2, AlertCircle, Pencil, Check, X } from 'lucide-react';
import { fetchTasks, createTask, updateTask, deleteTask, TaskItem } from '../../services/api';
import { useNotifications } from '../../context/NotificationContext';

const TasksPanel: React.FC = () => {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [newTask, setNewTask] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const { showToast } = useNotifications();

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
      showToast('Task Created', `"${created.title}" added to your tasks.`, 'info');
    } catch (err: any) {
      setError(err.message || 'Failed to create task');
    }
  };

  const handleToggle = async (id: string, currentCompleted: boolean) => {
    try {
      const updated = await updateTask(id, { completed: !currentCompleted });
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
      if (!currentCompleted) {
        showToast('Task Completed', `"${updated.title}" marked as complete!`, 'success');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to update task');
    }
  };

  const handleStartEdit = (task: TaskItem) => {
    setEditingTaskId(task.id);
    setEditingTitle(task.title);
  };

  const handleCancelEdit = () => {
    setEditingTaskId(null);
    setEditingTitle('');
  };

  const handleSaveEdit = async (id: string) => {
    if (!editingTitle.trim()) return;
    setIsSavingEdit(true);
    try {
      const updated = await updateTask(id, { title: editingTitle.trim() });
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
      setEditingTaskId(null);
      setEditingTitle('');
      showToast('Task Updated', `Task renamed to "${updated.title}".`, 'info');
    } catch (err: any) {
      setError(err.message || 'Failed to update task');
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleRemove = async (id: string) => {
    try {
      const target = tasks.find((t) => t.id === id);
      await deleteTask(id);
      setTasks((prev) => prev.filter((t) => t.id !== id));
      showToast('Task Removed', `"${target?.title || 'Task'}" was deleted.`, 'info');
    } catch (err: any) {
      setError(err.message || 'Failed to delete task');
    }
  };

  return (
    <div className="h-full flex flex-col min-h-0">
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

      <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
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
              title={task.completed ? 'Mark incomplete' : 'Mark completed'}
            >
              {task.completed ? (
                <CheckCircle size={18} className="text-emerald-400" />
              ) : (
                <Circle size={18} />
              )}
            </button>

            {editingTaskId === task.id ? (
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveEdit(task.id);
                    if (e.key === 'Escape') handleCancelEdit();
                  }}
                  autoFocus
                  className="flex-1 bg-gray-950 border border-cyan-500 rounded px-2.5 py-1 text-sm text-cyan-100 focus:outline-none"
                  placeholder="Task title..."
                />
                <button
                  onClick={() => handleSaveEdit(task.id)}
                  disabled={isSavingEdit || !editingTitle.trim()}
                  className="p-1 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/40 rounded transition-colors"
                  title="Save changes"
                >
                  <Check size={16} />
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="p-1 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded transition-colors"
                  title="Cancel edit"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <>
                <span className={`flex-1 text-sm ${task.completed ? 'line-through text-cyan-700' : 'text-cyan-200'}`}>
                  {task.title}
                </span>

                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleStartEdit(task)}
                    className="p-1 text-cyan-400 hover:text-cyan-200 hover:bg-cyan-950/40 rounded transition-colors"
                    title="Edit task"
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    onClick={() => handleRemove(task.id)}
                    className="p-1 text-red-400 hover:text-red-300 hover:bg-red-950/40 rounded transition-colors"
                    title="Delete task"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default TasksPanel;