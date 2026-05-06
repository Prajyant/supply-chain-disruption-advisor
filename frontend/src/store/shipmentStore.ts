import { create } from 'zustand';
import { ShipmentInput } from '../types';

interface ShipmentState {
  uploadedShipments: ShipmentInput[] | null;
  setUploadedShipments: (shipments: ShipmentInput[] | null) => void;
}

export const useShipmentStore = create<ShipmentState>((set) => ({
  uploadedShipments: null,
  setUploadedShipments: (shipments) => set({ uploadedShipments: shipments }),
}));
