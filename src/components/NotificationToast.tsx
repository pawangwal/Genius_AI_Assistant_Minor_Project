import React from 'react';
import { CheckCircle2, Info, AlertTriangle, Bell, X } from 'lucide-react';
import { useNotifications, ToastItem, ToastType } from '../context/NotificationContext';

const NotificationToast: React.FC = () => {
  const { toasts, dismissToast } = useNotifications();

  if (toasts.length === 0) return null;

  const renderIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />;
      case 'reminder':
        return <Bell size={18} className="text-purple-400 shrink-0 animate-bounce" />;
      case 'warning':
        return <AlertTriangle size={18} className="text-amber-400 shrink-0" />;
      case 'info':
      default:
        return <Info size={18} className="text-cyan-400 shrink-0" />;
    }
  };

  const getBorderColor = (type: ToastType) => {
    switch (type) {
      case 'success':
        return 'border-emerald-600/50 bg-gray-950/90 shadow-emerald-950/40';
      case 'reminder':
        return 'border-purple-600/60 bg-gray-950/90 shadow-purple-950/50';
      case 'warning':
        return 'border-amber-600/50 bg-gray-950/90 shadow-amber-950/40';
      case 'info':
      default:
        return 'border-cyan-600/50 bg-gray-950/90 shadow-cyan-950/40';
    }
  };

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-3">
      {toasts.map((toast: ToastItem) => (
        <div
          key={toast.id}
          className={`pointer-events-auto p-3.5 rounded-xl border backdrop-blur-md shadow-xl transition-all duration-300 animate-slide-in flex items-start justify-between gap-3 ${getBorderColor(
            toast.type
          )}`}
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5">{renderIcon(toast.type)}</div>
            <div>
              <h4 className="text-xs font-bold text-gray-200 tracking-wide">
                {toast.title}
              </h4>
              <p className="text-xs text-gray-400 mt-0.5 leading-snug">
                {toast.message}
              </p>
            </div>
          </div>

          <button
            onClick={() => dismissToast(toast.id)}
            className="text-gray-500 hover:text-gray-300 transition-colors p-1"
            title="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
};

export default NotificationToast;
