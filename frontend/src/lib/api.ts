/**
 * Unified API client bridge
 * Re-exports the core axios instance to maintain compatibility
 * with older components while using the new Switchboard logic.
 */

import apiClient from "./api/client";
export { apiClient };
export default apiClient;
