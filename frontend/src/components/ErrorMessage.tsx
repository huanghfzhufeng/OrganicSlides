import React from 'react';
import { AlertCircle, RefreshCw, XCircle, WifiOff } from 'lucide-react';

interface ErrorMessageProps {
    title?: string;
    message: string;
    details?: string[];
    type?: 'error' | 'warning' | 'network';
    onRetry?: () => void;
    onDismiss?: () => void;
    retryLabel?: string;
    className?: string;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({
    title,
    message,
    details,
    type = 'error',
    onRetry,
    onDismiss,
    retryLabel = '重试',
    className = '',
}) => {
    const configs = {
        error: {
            icon: XCircle,
            bgColor: 'bg-red-50',
            borderColor: 'border-red-200',
            textColor: 'text-red-600',
            iconColor: 'text-red-500',
            buttonBg: 'bg-red-100 hover:bg-red-200',
        },
        warning: {
            icon: AlertCircle,
            bgColor: 'bg-amber-50',
            borderColor: 'border-amber-200',
            textColor: 'text-amber-700',
            iconColor: 'text-amber-500',
            buttonBg: 'bg-amber-100 hover:bg-amber-200',
        },
        network: {
            icon: WifiOff,
            bgColor: 'bg-slate-50',
            borderColor: 'border-slate-200',
            textColor: 'text-slate-600',
            iconColor: 'text-slate-500',
            buttonBg: 'bg-slate-100 hover:bg-slate-200',
        },
    };

    const config = configs[type];
    const Icon = config.icon;

    return (
        <div
            className={`${config.bgColor} ${config.borderColor} ${config.textColor} 
                border rounded-2xl p-4 flex items-center gap-4 animate-in fade-in slide-in-from-top-2 duration-300 ${className}`}
        >
            <div className={`flex-shrink-0 ${config.iconColor}`}>
                <Icon size={24} />
            </div>
            <div className="flex-1 min-w-0">
                {title && <p className="text-sm font-bold mb-1">{title}</p>}
                <p className="text-sm font-medium">{message}</p>
                {details && details.length > 0 && (
                    <ul className="mt-2 space-y-1 text-xs opacity-90">
                        {details.map((detail) => (
                            <li key={detail}>{detail}</li>
                        ))}
                    </ul>
                )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
                {onRetry && (
                    <button
                        onClick={onRetry}
                        className={`${config.buttonBg} ${config.textColor} px-3 py-1.5 rounded-lg text-sm font-bold 
                            flex items-center gap-1.5 transition-colors`}
                    >
                        <RefreshCw size={14} />
                        {retryLabel}
                    </button>
                )}
                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        className={`${config.buttonBg} ${config.textColor} p-1.5 rounded-lg transition-colors`}
                    >
                        <XCircle size={16} />
                    </button>
                )}
            </div>
        </div>
    );
};

export default ErrorMessage;
