import { useEffect, Component, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useShipmentStore } from './store/shipmentStore';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { DigitalTwin } from './pages/DigitalTwin';
import { Chat } from './pages/Chat';
import { Settings } from './pages/Settings';
import { ShipmentDetail } from './pages/ShipmentDetail';
import { Playbooks } from './pages/Playbooks';
import { VesselTracking } from './pages/VesselTracking';
import { ViewModeProvider } from './context/ViewModeContext';
import { triggerShipmentPreload } from './services/shipmentPreloader';
import { AlertCircle } from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

class AppErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  state = { hasError: false, error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: any) {
    console.error('Application runtime error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen w-screen flex-col items-center justify-center bg-slate-950 p-6 text-center text-slate-100">
          <div className="max-w-md rounded-2xl border border-red-500/30 bg-slate-900 p-8 shadow-2xl">
            <AlertCircle className="mx-auto h-12 w-12 text-red-400 mb-4 animate-bounce" />
            <h2 className="text-xl font-bold text-white mb-2">Application Recovery</h2>
            <p className="text-xs text-slate-400 mb-6">
              An unexpected render error occurred: {this.state.error?.message || 'Unknown error'}.
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.href = '/';
              }}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded-xl transition shadow-lg"
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  const hydrateShipments = useShipmentStore((state) => state.hydrate);

  useEffect(() => {
    hydrateShipments();
    triggerShipmentPreload();
  }, [hydrateShipments]);

  return (
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ViewModeProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="shipments/:shipmentId" element={<ShipmentDetail />} />
                <Route path="digital-twin" element={<DigitalTwin />} />
                <Route path="chat" element={<Chat />} />
                <Route path="playbooks" element={<Playbooks />} />
                <Route path="vessel-tracking" element={<VesselTracking />} />
                <Route path="vessel%20tracking" element={<VesselTracking />} />
                <Route path="vessel tracking" element={<VesselTracking />} />
                <Route path="settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ViewModeProvider>
      </QueryClientProvider>
    </AppErrorBoundary>
  );
}

export default App;
