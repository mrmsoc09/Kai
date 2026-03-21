export interface ApiListResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface ApiError {
  message: string;
  status: number;
  details?: unknown;
}
