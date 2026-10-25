import React, { useState, useEffect } from 'react';
import { Bell, Plus, Trash2, Loader2, AlertCircle, Pencil, Check, X } from 'lucide-react';
import { fetchReminders, createReminder, updateReminder, deleteReminder, ReminderItem } from '../../services/api';
import { useNotifications } from '../../context/NotificationContext';

const RemindersPanel: React.FC = () => {
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [newReminder, setNewReminder] = useState('');
  const [newDateTime, setNewDateTime] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingReminderId, setEditingReminderId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [editingDueTime, setEditingDueTime] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const { showToast, browserPermission, requestBrowserPermission } = useNotifications();

  const loadReminders = async () => {
    try {
      setError(null);
      const items = await fetchReminders();
      setReminders(items);
    } catch (err: any) {
      setError(err.message || 'Unable to connect to reminders database.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReminders();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newReminder.trim() && newDateTime) {
      try {
        const created = await createReminder(newReminder.trim(), newDateTime);
        setReminders((prev) => [created, ...prev]);
        setNewReminder('');
        setNewDateTime('');
        showToast('Reminder Scheduled', `"${created.title}" scheduled for ${created.due_time}.`, 'reminder');
      } catch (err: any) {
        setError(err.message || 'Failed to create reminder');
      }
    }
  };

  const toInputDateTime = (dtStr: string): string => {
    try {
      const parsed = new Date(dtStr);
      if (isNaN(parsed.getTime())) {
        return dtStr.slice(0, 16);
      }
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
    } catch {
      return dtStr.slice(0, 16);
    }
  };

  const handleStartEdit = (reminder: ReminderItem) => {
    setEditingReminderId(reminder.id);
    setEditingTitle(reminder.title);
    setEditingDueTime(toInputDateTime(reminder.due_time));
  };

  const handleCancelEdit = () => {
    setEditingReminderId(null);
    setEditingTitle('');
    setEditingDueTime('');
  };

  const handleSaveEdit = async (id: string) => {
    if (!editingTitle.trim()) return;
    setIsSavingEdit(true);
    try {
      const updated = await updateReminder(id, {
        title: editingTitle.trim(),
        due_time: editingDueTime ? new Date(editingDueTime).toISOString() : undefined,
      });
      setReminders((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setEditingReminderId(null);
      setEditingTitle('');
      setEditingDueTime('');
      showToast('Reminder Updated', `"${updated.title}" updated for ${updated.due_time}.`, 'reminder');
    } catch (err: any) {
      setError(err.message || 'Failed to update reminder');
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleRemove = async (id: string) => {
    try {
      const target = reminders.find((r) => r.id === id);
      await deleteReminder(id);
      setReminders((prev) => prev.filter((r) => r.id !== id));
      showToast('Reminder Dismissed', `"${target?.title || 'Reminder'}" was dismissed.`, 'info');
    } catch (err: any) {
      setError(err.message || 'Failed to delete reminder');
    }
  };

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center justify-between mb-6 border-b border-purple-900/40 pb-3">
        <div className="flex items-center">
          <Bell className="text-purple-400 mr-2" size={24} />
          <div>
            <h2 className="text-xl font-bold text-purple-300">Persistent Reminders</h2>
            <p className="text-xs text-purple-600">PostgreSQL-backed async reminders store</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {browserPermission === 'default' && (
            <button
              onClick={requestBrowserPermission}
              className="text-[11px] text-purple-300 bg-purple-950/60 border border-purple-800/60 hover:bg-purple-900/50 px-2.5 py-1 rounded-md transition-colors"
            >
              Enable Browser Alerts
            </button>
          )}
          {loading && <Loader2 className="animate-spin text-purple-400" size={18} />}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-950/50 border border-red-800 rounded-lg text-red-300 text-xs flex items-center gap-2">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mb-6 space-y-3">
        <input
          type="text"
          value={newReminder}
          onChange={(e) => setNewReminder(e.target.value)}
          placeholder="Reminder title..."
          className="w-full bg-black/40 border border-purple-900/60 rounded-lg px-4 py-2 text-white placeholder-purple-700 focus:outline-none focus:border-purple-500 text-sm"
        />
        <div className="flex gap-2">
          <input
            type="datetime-local"
            value={newDateTime}
            onChange={(e) => setNewDateTime(e.target.value)}
            className="flex-1 bg-black/40 border border-purple-900/60 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500 text-sm"
          />
          <button
            type="submit"
            className="bg-purple-900/60 hover:bg-purple-800/80 text-purple-300 px-4 rounded-lg flex items-center transition-colors"
          >
            <Plus size={18} />
          </button>
        </div>
      </form>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
        {reminders.length === 0 && !loading && (
          <div className="text-center py-10 text-purple-700 text-sm">
            No active reminders scheduled.
          </div>
        )}
        {reminders.map((reminder) => (
          <div
            key={reminder.id}
            className="flex items-center gap-3 p-3 bg-black/30 border border-purple-900/40 rounded-lg group hover:border-purple-700/50 transition-all"
          >
            {editingReminderId === reminder.id ? (
              <div className="flex-1 flex flex-col gap-2">
                <input
                  type="text"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  autoFocus
                  placeholder="Reminder title..."
                  className="w-full bg-gray-950 border border-purple-500 rounded px-2.5 py-1 text-sm text-purple-100 focus:outline-none"
                />
                <div className="flex items-center gap-2">
                  <input
                    type="datetime-local"
                    value={editingDueTime}
                    onChange={(e) => setEditingDueTime(e.target.value)}
                    className="flex-1 bg-gray-950 border border-purple-500/70 rounded px-2.5 py-1 text-xs text-purple-200 focus:outline-none"
                  />
                  <button
                    onClick={() => handleSaveEdit(reminder.id)}
                    disabled={isSavingEdit || !editingTitle.trim()}
                    className="p-1.5 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/40 rounded transition-colors"
                    title="Save reminder"
                  >
                    <Check size={16} />
                  </button>
                  <button
                    onClick={handleCancelEdit}
                    className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded transition-colors"
                    title="Cancel edit"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex-1">
                  <div className="text-purple-200 text-sm font-medium">
                    {reminder.title}
                  </div>
                  <div className="text-xs text-purple-400 font-mono mt-0.5">
                    Due: {reminder.due_time}
                  </div>
                </div>

                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleStartEdit(reminder)}
                    className="p-1 text-purple-400 hover:text-purple-200 hover:bg-purple-950/40 rounded transition-colors"
                    title="Edit reminder"
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    onClick={() => handleRemove(reminder.id)}
                    className="p-1 text-red-400 hover:text-red-300 hover:bg-red-950/40 rounded transition-colors"
                    title="Dismiss reminder"
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

export default RemindersPanel;