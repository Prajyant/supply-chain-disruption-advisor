import { create } from 'zustand';
import { User } from '../types/index';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  authReady: boolean;
  setAuth: (user: User, token: string) => void;
  setAuthReady: (authReady: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  authReady: false,
  setAuth: (user, token) =>
    set({ user, token, isAuthenticated: true }),
  setAuthReady: (authReady) => set({ authReady }),
  logout: () =>
    set({ user: null, token: null, isAuthenticated: false }),
}));
