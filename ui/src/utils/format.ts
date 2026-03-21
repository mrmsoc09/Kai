export const formatTimestamp = (value: string): string =>
  new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

export const formatConfidence = (value: number): string => `${Math.round(value * 100)}%`;
