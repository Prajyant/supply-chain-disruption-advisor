import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { DigitalTwin } from './pages/DigitalTwin';
import { Chat } from './pages/Chat';
import { Settings } from './pages/Settings';
import { ShipmentDetail } from './pages/ShipmentDetail';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="shipments/:shipmentId" element={<ShipmentDetail />} />
            <Route path="digital-twin" element={<DigitalTwin />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
