import { useState, useEffect, useRef, useCallback } from 'react';

interface UseSSEOptions {
    url: string;
    onMessage: (data: any) => void;
    onError?: (error: string) => void;
    maxRetries?: number;
    enabled?: boolean;
}

export function useSSE({ url, onMessage, onError, maxRetries = 3, enabled = true }: UseSSEOptions) {
    const [connected, setConnected] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const eventSourceRef = useRef<EventSource | null>(null);
    const closedRef = useRef(false);

    const close = useCallback(() => {
        closedRef.current = true;
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setConnected(false);
    }, []);

    useEffect(() => {
        if (!enabled || !url) return;
        closedRef.current = false;

        const connect = () => {
            if (closedRef.current) return;

            const es = new EventSource(url);
            eventSourceRef.current = es;

            es.onopen = () => {
                setConnected(true);
                setRetryCount(0);
            };

            es.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    onMessage(data);
                    // If complete or fatal error, close permanently
                    if (data.type === 'complete' || data.type === 'error') {
                        close();
                    }
                } catch {
                    // ignore parse errors
                }
            };

            es.onerror = () => {
                es.close();
                eventSourceRef.current = null;
                setConnected(false);

                if (closedRef.current) return;

                setRetryCount(prev => {
                    const next = prev + 1;
                    if (next <= maxRetries) {
                        const delay = Math.min(1000 * Math.pow(2, next - 1), 8000);
                        setTimeout(connect, delay);
                    } else {
                        onError?.('连接中断，请检查网络后重试');
                    }
                    return next;
                });
            };
        };

        connect();

        return () => {
            close();
        };
    }, [url, enabled]); // intentionally exclude onMessage/onError to avoid reconnect on re-render

    return { connected, retryCount, close };
}
