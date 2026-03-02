/**
 * Unified API client bridge
 * Re-exports the core axios instance to maintain compatibility.
 */

import apiClient from "./api/client";
export { apiClient };
export default apiClient;
