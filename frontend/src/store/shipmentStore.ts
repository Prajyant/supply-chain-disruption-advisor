import { create } from 'zustand';
import { ShipmentInput } from '../types';
import { shipmentApi } from '../services/api';

const LOCAL_STORAGE_KEY = 'uploaded_shipments';

interface ShipmentState {
  uploadedShipments: ShipmentInput[] | null;
  isHydrated: boolean;
  setUploadedShipments: (shipments: ShipmentInput[] | null) => void;
  hydrate: () => Promise<void>;
}

export const useShipmentStore = create<ShipmentState>((set, get) => ({
  uploadedShipments: null,
  isHydrated: false,

  setUploadedShipments: (shipments) => {
    set({ uploadedShipments: shipments });
    // Persist to localStorage immediately
    if (shipments) {
      try {
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(shipments));
      } catch {
        // Storage full or unavailable — ignore
      }
    } else {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    }
  },

  hydrate: async () => {
    if (get().isHydrated) return;

    // 1. Restore from localStorage instantly (no network needed)
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (stored) {
        const shipments = JSON.parse(stored) as ShipmentInput[];
        if (shipments.length > 0) {
          set({ uploadedShipments: shipments, isHydrated: true });
          return;
        }
      }
    } catch {
      // Corrupted data — ignore
    }

    // 2. Try DynamoDB as fallback (for cross-device persistence)
    try {
      const res = await shipmentApi.getUploadedShipments();
      const data = res.data;
      if (data.shipments && data.shipments.length > 0) {
        set({ uploadedShipments: data.shipments, isHydrated: true });
        // Also cache locally for next reload
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(data.shipments));
        return;
      }
    } catch {
      // DynamoDB unavailable — no problem
    }

    set({ isHydrated: true });
  },
}));
