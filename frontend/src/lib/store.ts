import { create } from 'zustand'

type AppState = {
  demoMode: boolean
  sidebarOpen: boolean
  setDemoMode: (value: boolean) => void
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>((set) => ({
  demoMode: false,
  sidebarOpen: typeof window === 'undefined' || window.innerWidth > 760,
  setDemoMode: (demoMode) => set({ demoMode }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}))
