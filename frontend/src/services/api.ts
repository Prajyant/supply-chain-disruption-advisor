import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

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

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
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
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
};

export const riskApi = {
  getRisks: () => api.get('/risks'),
  getRisk: (id: string) => api.get(`/risks/${id}`),
};

export const networkApi = {
  getNetwork: () => api.get('/network'),
  getNode: (id: string) => api.get(`/api/node/${id}`),
  getNodeImpact: (id: string) => api.get(`/api/node/${id}/impact`),
  getNodeContext: (id: string) => api.get(`/api/node/${id}/context`),
  propagateRisk: () => api.post('/graph/propagate'),
};

export const chatApi = {
  chat: (question: string, topK = 5) =>
    api.post('/chat', { question, top_k: topK }),
};

export const ingestApi = {
  ingest: (data: {
    supplier_emails_path?: string;
    news_feed_path?: string;
    inventory_path?: string;
    use_realtime_news?: boolean;
    use_live_emails?: boolean;
  }) => api.post('/ingest', data),
};

export const shipmentApi = {
  getShipments: () => api.get('/shipments'),
  getShipmentsByNode: (nodeId: string) => api.get(`/shipments/node/${nodeId}`),
};

export default api;
