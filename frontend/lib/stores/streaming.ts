import { create } from 'zustand'

interface StreamEvent {
  id: string
  type: string
  timestamp: string
  data: Record<string, unknown>
}

interface StreamingState {
  isConnected: boolean
  events: StreamEvent[]
  addEvent: (event: StreamEvent) => void
  clearEvents: () => void
  setConnected: (connected: boolean) => void
}

export const useStreamingStore = create<StreamingState>((set) => ({
  isConnected: false,
  events: [],

  addEvent: (event) => set((state) => ({
    events: [event, ...state.events].slice(0, 100), // Keep last 100 events
  })),

  clearEvents: () => set({ events: [] }),

  setConnected: (connected) => set({ isConnected: connected }),
}))
