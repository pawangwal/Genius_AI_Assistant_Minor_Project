import React, { createContext, useContext, useState, useRef, useEffect, ReactNode, useCallback } from 'react';
import { fetchReminders } from '../services/api';

export type ToastType = 'success' | 'info' | 'warning' | 'reminder';

export interface ToastItem {
  id: string;
  title: string;
  message: string;
  type: ToastType;
  createdAt: number;
}

interface NotificationContextType {
  toasts: ToastItem[];
  showToast: (title: string, message: string, type?: ToastType) => void;
  dismissToast: (id: string) => void;
  browserPermission: NotificationPermission | 'unsupported';
  requestBrowserPermission: () => Promise<boolean>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [browserPermission, setBrowserPermission] = useState<NotificationPermission | 'unsupported'>(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      return Notification.permission;
    }
    return 'unsupported';
  });

  const notifiedReminderIds = useRef<Set<string>>(new Set());
  const isInitialScanRef = useRef<boolean>(true);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((title: string, message: string, type: ToastType = 'info') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const newToast: ToastItem = {
      id,
      title,
      message,
      type,
      createdAt: Date.now(),
    };

    setToasts((prev) => [...prev, newToast]);

    // Native browser notification if user gave permission
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(title, {
          body: message,
          icon: '/favicon.ico',
        });
      } catch {
        // Ignored if browser policy blocks notification
      }
    }

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      dismissToast(id);
    }, 5000);
  }, [dismissToast]);

  const requestBrowserPermission = async (): Promise<boolean> => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      setBrowserPermission('unsupported');
      return false;
    }
    try {
      const permission = await Notification.requestPermission();
      setBrowserPermission(permission);
      return permission === 'granted';
    } catch {
      return false;
    }
  };

  // Due reminder background checker (polls every 15 seconds while app is open)
  useEffect(() => {
    const checkDueReminders = async () => {
      try {
        const reminders = await fetchReminders();
        const nowMs = Date.now();
        const isFirstRun = isInitialScanRef.current;

        for (const rem of reminders) {
          if (rem.completed) continue;
          if (notifiedReminderIds.current.has(rem.id)) continue;

          // Parse due_time: could be ISO "2026-10-25T18:00" or similar
          const dueMs = Date.parse(rem.due_time);
          if (!isNaN(dueMs)) {
            // Suppress initial spam for reminders overdue by more than 10 minutes
            if (isFirstRun && dueMs < nowMs - 10 * 60 * 1000) {
              notifiedReminderIds.current.add(rem.id);
              continue;
            }

            // If due_time is passed or due within 30 seconds
            if (dueMs <= nowMs + 30000) {
              notifiedReminderIds.current.add(rem.id);
              showToast(
                'Reminder Due',
                `"${rem.title}" is now due!`,
                'reminder'
              );
            }
          }
        }
        isInitialScanRef.current = false;
      } catch {
        // Silently skip if database or backend is temporarily restarting
      }
    };

    checkDueReminders();
    const interval = setInterval(checkDueReminders, 15000);
    return () => clearInterval(interval);
  }, [showToast]);

  return (
    <NotificationContext.Provider
      value={{
        toasts,
        showToast,
        dismissToast,
        browserPermission,
        requestBrowserPermission,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
};
