import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const AUTH_PATHS = new Set(['/auth/login', '/auth/refresh']);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const requestUrl = originalRequest?.url || '';

    if (!originalRequest || AUTH_PATHS.has(requestUrl)) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('Missing refresh token');
        }
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, null, {
          params: { refresh_token: refreshToken },
        });

        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('auth_user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// ==================== Phase 3: Auth API ====================

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
};

// ==================== Risk API ====================

export const riskApi = {
  getRisks: () => api.get('/risks'),
  getRisk: (id: string) => api.get(`/risks/${id}`),
};

// ==================== Network API ====================

export const networkApi = {
  getNetwork: () => api.get('/network'),
  getNode: (id: string) => api.get(`/api/node/${id}`),
  getNodeImpact: (id: string) => api.get(`/api/node/${id}/impact`),
  getNodeContext: (id: string) => api.get(`/api/node/${id}/context`),
  propagateRisk: () => api.post('/graph/propagate'),
};

// ==================== Chat API ====================

export const chatApi = {
  chat: (question: string, topK = 5) =>
    api.post('/chat', { question, top_k: topK }),
};

// ==================== Ingest API ====================

export const ingestApi = {
  ingest: (data: {
    supplier_emails_path?: string;
    news_feed_path?: string;
    inventory_path?: string;
    use_realtime_news?: boolean;
    use_live_emails?: boolean;
  }) => api.post('/ingest', data),
};

// ==================== Shipment API (risk-analysis + Phase 3) ====================

export const shipmentApi = {
  // Phase-3: shipment tracking endpoints
  getShipments: () => api.get('/shipments'),
  getShipmentsByNode: (nodeId: string) => api.get(`/shipments/node/${nodeId}`),
  // risk-analysis: CSV upload & Strands risk analysis
  uploadCsv: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/shipments/upload-csv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  runStrandsRisk: (shipment: any, question?: string) =>
    api.post('/agents/strands/shipment-risk', { shipment, question }),
};

// ==================== Agent API (risk-analysis) ====================

export const agentApi = {
  getStrandsStatus: () => api.get('/agents/strands/status'),
};

// ==================== Flight API (risk-analysis) ====================

export const flightApi = {
  getFlightByCallsign: (callsign: string) => api.get(`/flights/${callsign}`),
};

// ==================== Playbook API (Phase 3) ====================

export const playbookApi = {
  getPlaybooks: () => api.get('/playbooks'),
  getExecutions: () => api.get('/playbooks/executions'),
  togglePlaybook: (id: string, enabled: boolean) =>
    api.patch(`/playbooks/${id}?enabled=${enabled}`),
  submitFeedback: (executionId: string, decision: string, comment?: string) =>
    api.post(
      `/playbooks/executions/${executionId}/feedback?decision=${decision}${comment ? '&comment=' + encodeURIComponent(comment) : ''}`
    ),
  simulate: (playbookId: string) =>
    api.post(`/playbooks/${playbookId}/simulate`),
};

// ==================== Feedback API (Phase 3) ====================

export const feedbackApi = {
  getStats: () => api.get('/feedback/stats'),
  getHistory: (limit = 50) => api.get(`/feedback/history?limit=${limit}`),
};

export default api;
