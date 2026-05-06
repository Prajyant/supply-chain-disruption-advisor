import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const hydrateShipments = useShipmentStore((state) => state.hydrate);

  useEffect(() => {
    hydrateShipments();
    triggerShipmentPreload();
  }, [hydrateShipments]);

  return (
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
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ViewModeProvider>
    </QueryClientProvider>
  );
}

export default App;
