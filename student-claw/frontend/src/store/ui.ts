"use client";

/**
 * Lightweight UI state (blueprint §6.3 — Zustand for modals/sidebar).
 * Keeps interactive chrome state out of React Query / server data.
 */

import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebar: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: false, // closed by default on mobile; lg+ shows it via CSS
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebar: (open) => set({ sidebarOpen: open }),
}));
