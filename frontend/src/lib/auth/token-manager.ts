/**
 * Token Manager - Store/Retrieve JWT Tokens
 */

const TOKEN_KEYS = {
  ACCESS: "access_token",
  REFRESH: "refresh_token",
};

// Simple cookie helpers
const setCookie = (name: string, value: string, days = 7) => {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${value}; expires=${expires}; path=/; SameSite=Lax`;
};

const getCookie = (name: string) => {
  if (typeof document === "undefined") return null;
  return document.cookie.split("; ").reduce((r, v) => {
    const parts = v.split("=");
    return parts[0] === name ? decodeURIComponent(parts[1]) : r;
  }, "");
};

const removeCookie = (name: string) => {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
};

export const tokenManager = {
  // Get access token
  getAccessToken: (): string | null => {
    return getCookie(TOKEN_KEYS.ACCESS) || null;
  },

  // Get refresh token
  getRefreshToken: (): string | null => {
    return getCookie(TOKEN_KEYS.REFRESH) || null;
  },

  // Set tokens
  setTokens: (access: string, refresh: string): void => {
    setCookie(TOKEN_KEYS.ACCESS, access);
    setCookie(TOKEN_KEYS.REFRESH, refresh);
  },

  // Set access token only (useful for refresh)
  setAccessToken: (access: string): void => {
    setCookie(TOKEN_KEYS.ACCESS, access);
  },

  // Clear tokens
  clearTokens: (): void => {
    removeCookie(TOKEN_KEYS.ACCESS);
    removeCookie(TOKEN_KEYS.REFRESH);
  },

  // Check if tokens exist
  hasTokens: (): boolean => {
    return !!(tokenManager.getAccessToken() && tokenManager.getRefreshToken());
  },
};
