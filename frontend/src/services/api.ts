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

// Response interceptor — log errors but don't redirect
api.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error)
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
  getNode: (id: string) => api.get(`/node/${id}`),
  getNodeImpact: (id: string) => api.get(`/node/${id}/impact`),
  getNodeContext: (id: string) => api.get(`/node/${id}/context`),
  propagateRisk: () => api.post('/graph/propagate'),
  scoreNodes: () => api.post('/graph/score-nodes'),
};

// ==================== Chat API ====================

export const chatApi = {
  chat: (question: string, topK = 5) =>
    api.post('/chat', { question, top_k: topK }),
  getContext: () => api.get('/chat/context'),
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
  // Preload: batch-analyze all shipments in background
  preloadAnalyses: (shipments: any[]) => api.post('/shipments/preload', shipments),
  getPreloadedAnalysis: (shipmentId: string) => api.get(`/shipments/${shipmentId}/preloaded`),
  getPreloadStatus: () => api.get('/shipments/preload/status'),
  getRiskSummary: () => api.get('/shipments/risk-summary'),
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
  // Fetch previously uploaded shipments from DynamoDB (persists across reloads)
  getUploadedShipments: () => api.get('/db/uploaded-shipments'),
  runStrandsRisk: (shipment: any, question?: string) =>
    api.post('/agents/strands/shipment-risk', { shipment, question }),
  generateResolutionPackage: (shipment: any) =>
    api.post('/shipments/resolution-package', { shipment, intelligence_events: [], use_live_intelligence: true }),
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

// ==================== Maritime Intelligence API ====================

export const maritimeApi = {
  getVesselRegistry: (imo: string) => api.get(`/maritime/vessel-registry/${imo}`),
  getRouteDistance: (origin: string, destination: string, speedKnots = 14) =>
    api.get('/maritime/route-distance', { params: { origin, destination, speed_knots: speedKnots } }),
  getRouteDeviation: (vesselLat: number, vesselLon: number, origin: string, destination: string) =>
    api.get('/maritime/route-deviation', { params: { vessel_lat: vesselLat, vessel_lon: vesselLon, origin, destination } }),
  screenVesselSanctions: (imo: string, vesselName = '') =>
    api.get(`/maritime/sanctions/vessel/${imo}`, { params: { vessel_name: vesselName } }),
  screenEntitySanctions: (name: string) => api.get(`/maritime/sanctions/entity/${name}`),
  screenRouteSanctions: (countries: string[]) =>
    api.get('/maritime/sanctions/route', { params: { countries: countries.join(',') } }),
  getRouteTariffs: (originCountry: string, destCountry: string, category = 'electronics') =>
    api.get('/maritime/tariffs', { params: { origin_country: originCountry, destination_country: destCountry, product_category: category } }),
  getPortCongestion: (portName: string) => api.get(`/maritime/port-congestion/${portName}`),
  getAllPortCongestion: () => api.get('/maritime/port-congestion'),
  resolveMMSI: (mmsi: string) => api.get(`/maritime/identity/resolve-mmsi/${mmsi}`),
};

export default api;
