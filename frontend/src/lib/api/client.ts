/**
 * Axios client for API requests
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { tokenManager } from '@/lib/auth/token-manager';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';

// Handle API URL that might already include /api/v1
const baseURL = API_URL.includes('/api/')
    ? API_URL
    : `${API_URL}/api/${API_VERSION}`;

// Create axios instance
const apiClient: AxiosInstance = axios.create({
    baseURL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 120000, // 120 seconds for batched generation
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // Get token from localStorage
        const token = tokenManager.getAccessToken();

        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor - Handle token refresh
apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // If 401 and not already retried, try to refresh token
        if (error.response?.status === 401 && !originalRequest?._retry) {
            originalRequest._retry = true;

            try {
                const refreshToken = tokenManager.getRefreshToken();

                if (!refreshToken) {
                    throw new Error('No refresh token');
                }

                // Call refresh endpoint
                const response = await axios.post(
                    `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/v1/auth/token/refresh/`,
                    { refresh: refreshToken }
                );

                const { access } = response.data;

                // Store new access token
                tokenManager.setAccessToken(access);

                // Retry original request with new token
                if (originalRequest.headers) {
                    originalRequest.headers.Authorization = `Bearer ${access}`;
                }

                return apiClient(originalRequest);
            } catch (refreshError) {
                // Refresh failed - logout user
                tokenManager.clearTokens();
                window.location.href = '/auth/login';
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

export default apiClient;

// Helper function to handle API errors
export const getErrorMessage = (error: unknown): string => {
    if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<{ error?: string; detail?: string; message?: string }>;

        if (axiosError.response?.data) {
            return (
                axiosError.response.data.error ||
                axiosError.response.data.detail ||
                axiosError.response.data.message ||
                'An error occurred'
            );
        }

        return axiosError.message || 'Network error';
    }

    return 'An unexpected error occurred';
};
