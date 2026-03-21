import { useCallback, useEffect, useState } from 'react';
import { systemService } from '../api';
import { useAppStore } from '../store/appStore';

export function useSystemStatus() {
  const systemStatus = useAppStore((state) => state.systemStatus);
  const setSystemStatus = useAppStore((state) => state.setSystemStatus);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const status = await systemService.status();
      setSystemStatus(status);
    } catch (statusError) {
      setError(statusError instanceof Error ? statusError.message : 'Unable to fetch system status.');
    } finally {
      setIsLoading(false);
    }
  }, [setSystemStatus]);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  return {
    systemStatus,
    isLoading,
    error,
    refreshStatus,
  };
}
