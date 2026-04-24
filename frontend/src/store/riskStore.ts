import { create } from 'zustand';
import { RiskAssessment } from '../types';

interface RiskState {
  risks: RiskAssessment[];
  loading: boolean;
  error: string | null;
  setRisks: (risks: RiskAssessment[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useRiskStore = create<RiskState>((set) => ({
  risks: [],
  loading: false,
  error: null,
  setRisks: (risks) => set({ risks }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
