import { create } from 'zustand';
import { User } from '../types/index';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  setAuth: (user: User, token: string) => void;
  hydrateAuth: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isHydrated: false,
  setAuth: (user, token) =>
    set(() => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('auth_user', JSON.stringify(user));
      return { user, token, isAuthenticated: true, isHydrated: true };
    }),
  hydrateAuth: () =>
    set(() => {
      const token = localStorage.getItem('access_token');
      const userJson = localStorage.getItem('auth_user');

      if (!token || !userJson) {
        return { user: null, token: null, isAuthenticated: false, isHydrated: true };
      }

      try {
        const user = JSON.parse(userJson) as User;
        return { user, token, isAuthenticated: true, isHydrated: true };
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('auth_user');
        return { user: null, token: null, isAuthenticated: false, isHydrated: true };
      }
    }),
  logout: () =>
    set(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('auth_user');
      return { user: null, token: null, isAuthenticated: false, isHydrated: true };
    }),
}));
