import { create } from 'zustand'

interface StreamEvent {
  id: string
  type: string
  timestamp: string
  data: Record<string, unknown>
}

interface StreamingState {
  isConnected: boolean
  connectionStatus: 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
  events: StreamEvent[]
  driftAlerts: Array<{ kappa: number; severity: string; timestamp: string }>
  addEvent: (event: StreamEvent) => void
  addDriftAlert: (alert: { kappa: number; severity: string; timestamp: string }) => void
  clearEvents: () => void
  setConnected: (connected: boolean) => void
  setConnectionStatus: (status: 'connecting' | 'connected' | 'reconnecting' | 'disconnected') => void
}

export const useStreamingStore = create<StreamingState>((set) => ({
  isConnected: false,
  connectionStatus: 'disconnected',
  events: [],
  driftAlerts: [],

  addEvent: (event) => set((state) => ({
    events: [event, ...state.events].slice(0, 100), // Keep last 100 events
  })),

  addDriftAlert: (alert) => set((state) => ({
    driftAlerts: [alert, ...state.driftAlerts].slice(0, 20),
  })),

  clearEvents: () => set({ events: [] }),

  setConnected: (connected) => set({
    isConnected: connected,
    connectionStatus: connected ? 'connected' : 'disconnected',
  }),

  setConnectionStatus: (status) => set({
    connectionStatus: status,
    isConnected: status === 'connected',
  }),
}))
