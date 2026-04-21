import { useEffect } from 'react';

interface ToastProps {
  message: string;
  onClose: () => void;
  autoCloseMs?: number;
  type?: 'error' | 'success' | 'info';
}

export default function Toast({ message, onClose, autoCloseMs = 5000, type = 'error' }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, autoCloseMs);
    return () => clearTimeout(timer);
  }, [onClose, autoCloseMs]);

  const colorMap = {
    error: 'bg-brand-red/20 border-brand-red text-brand-red',
    success: 'bg-brand-green/20 border-brand-green text-brand-green',
    info: 'bg-databricks-primary/20 border-databricks-primary text-databricks-primary',
  };

  return (
    <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg border ${colorMap[type]} max-w-md shadow-lg`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm">{message}</p>
        <button onClick={onClose} className="text-gray-600 hover:text-gray-800">
          &times;
        </button>
      </div>
    </div>
  );
}
