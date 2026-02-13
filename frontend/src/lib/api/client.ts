/**
 * Axios client for API requests
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

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
    timeout: 30000, // 30 seconds for article generation
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use(
    (config) => {
        // Get token from localStorage
        const token = localStorage.getItem('access_token');

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config;

        // Handle 401 (token expired)
        if (error.response?.status === 401 && originalRequest) {
            try {
                // Try to refresh token
                const refreshToken = localStorage.getItem('refresh_token');

                if (refreshToken) {
                    const response = await axios.post(`${API_URL}/api/token/refresh/`, {
                        refresh: refreshToken,
                    });

                    const { access } = response.data;
                    localStorage.setItem('access_token', access);

                    // Retry original request
                    originalRequest.headers.Authorization = `Bearer ${access}`;
                    return apiClient(originalRequest);
                }
            } catch (refreshError) {
                // Refresh failed, redirect to login
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/login';
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
