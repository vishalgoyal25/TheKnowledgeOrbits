/**
 * Axios client for API requests
 */

import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
} from "axios";
import { tokenManager } from "@/lib/auth/token-manager";
import { createLogger } from "@/lib/logger";

const logger = createLogger("API");

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || "v1";

// Handle API URL that might already include /api/v1 or missing HTTP prefix
let cleanApiUrl = API_URL.replace(/\/+$/, "");

if (!cleanApiUrl.startsWith("http://") && !cleanApiUrl.startsWith("https://")) {
  cleanApiUrl = `https://${cleanApiUrl}`;
}

const baseURL = cleanApiUrl.includes("/api/")
  ? cleanApiUrl
  : `${cleanApiUrl}/api/${API_VERSION}`;

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
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
    logger.error("Request configuration error:", error);
    return Promise.reject(error);
  },
);

// Response interceptor - Handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // If 401 and not already retried, try to refresh token
    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = tokenManager.getRefreshToken();

        if (!refreshToken) {
          throw new Error("No refresh token");
        }

        // Call refresh endpoint
        const response = await axios.post(
          `${
            process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
          }/api/v1/auth/token/refresh/`,
          { refresh: refreshToken },
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
        logger.warn("Token refresh failed, logging out user...", refreshError);
        tokenManager.clearTokens();
        window.location.href = "/auth/login";
        return Promise.reject(refreshError);
      }
    }

    logger.error(
      `Response error [${error.response?.status}]:`,
      error.response?.data || error.message,
    );
    return Promise.reject(error);
  },
);

export default apiClient;

/**
 * Global API error handler — parses Axios errors and returns a human-readable string.
 * It checks nested data objects for common backend error keys (message, error, detail).
 *
 * @param error - The caught error object
 * @returns A user-friendly error message
 */
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{
      error?: string;
      detail?: string | Record<string, string[]>;
      message?: string;
    }>;

    if (axiosError.response?.data) {
      const { data } = axiosError.response;

      // Check for direct message
      if (data.message) return data.message;
      if (data.error) return data.error;

      // Handle Django Rest Framework 'detail' field
      if (typeof data.detail === "string") return data.detail;

      // Handle validation errors (objects)
      if (typeof data.detail === "object" && data.detail !== null) {
        return Object.entries(data.detail)
          .map(
            ([key, value]) =>
              `${key}: ${Array.isArray(value) ? value.join(", ") : value}`,
          )
          .join(" | ");
      }

      return "An error occurred on the server";
    }

    return axiosError.message || "Network error. Please check your connection.";
  }

  if (error instanceof Error) return error.message;

  return "An unexpected error occurred";
};
