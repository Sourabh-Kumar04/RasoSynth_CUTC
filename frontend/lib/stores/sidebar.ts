import { create } from 'zustand'

interface SidebarState {
  collapsed: boolean
  activeSection: string
  toggleCollapsed: () => void
  setActiveSection: (section: string) => void
}

export const useSidebarStore = create<SidebarState>((set) => ({
  collapsed: false,
  activeSection: 'overview',
  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
  setActiveSection: (section) => set({ activeSection: section }),
}))
