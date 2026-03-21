import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios';
import { useAppStore } from '../store/appStore';
import { appConfig } from '../utils/config';
import { tokenStorage } from '../utils/storage';
import type { ApiError } from '../types';

const apiClient: AxiosInstance = axios.create({
  baseURL: appConfig.apiBaseUrl,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const storeToken = useAppStore.getState().auth.token;
  const token = storeToken ?? tokenStorage.getToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string; detail?: string | Record<string, unknown> }>) => {
    const status = error.response?.status ?? 500;

    if (status === 401) {
      useAppStore.getState().clearAuth();
    }

    const detail = error.response?.data?.detail;
    const detailMessage =
      typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string'
          ? detail.message
          : undefined;

    const apiError: ApiError = {
      status,
      message: error.response?.data?.message ?? detailMessage ?? error.message ?? 'Request failed',
      details: error.response?.data,
    };

    return Promise.reject(apiError);
  },
);

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.request<T>(config);
  return response.data;
}

export { apiClient };
