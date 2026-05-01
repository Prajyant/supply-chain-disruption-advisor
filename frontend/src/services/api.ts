import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const riskApi = {
  getRisks: () => api.get('/risks'),
  getRisk: (id: string) => api.get(`/risks/${id}`),
};

export const networkApi = {
  getNetwork: () => api.get('/network'),
  getNode: (id: string) => api.get(`/api/node/${id}`),
  getNodeImpact: (id: string) => api.get(`/api/node/${id}/impact`),
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
  uploadCsv: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/shipments/upload-csv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
  runStrandsRisk: (shipment: any, query?: string) =>
    api.post('/agents/strands/shipment-risk', { shipment, query }),
};

export const agentApi = {
  getStrandsStatus: () => api.get('/agents/strands/status'),
};

export const flightApi = {
  getFlightByCallsign: (callsign: string) => api.get(`/flights/${callsign}`),
};

export default api;
