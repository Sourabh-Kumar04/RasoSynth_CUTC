import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api/client'

// Query Keys
export const queryKeys = {
  jobs: ['jobs'] as const,
  job: (id: string) => ['jobs', id] as const,
  datasets: ['datasets'] as const,
  dataset: (id: string) => ['datasets', id] as const,
  providers: ['providers'] as const,
  provider: (id: string) => ['providers', id] as const,
  providerMetrics: (id: string) => ['providers', id, 'metrics'] as const,
  metrics: ['metrics'] as const,
  health: ['health'] as const,
}

// Jobs Hooks
export function useJobs(params?: { status?: string; page?: number; pageSize?: number }) {
  return useQuery({
    queryKey: [...queryKeys.jobs, params],
    queryFn: () => api.getJobs(params),
    refetchInterval: 30000, // Refresh every 30 seconds
  })
}

export function useJob(id: string) {
  return useQuery({
    queryKey: queryKeys.job(id),
    queryFn: () => api.getJob(id),
    enabled: !!id,
  })
}

export function useCreateJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: any) => api.createJob(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

export function useCancelJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => api.cancelJob(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
    },
  })
}

// Datasets Hooks
export function useDatasets(params?: { modality?: string; page?: number; pageSize?: number }) {
  return useQuery({
    queryKey: [...queryKeys.datasets, params],
    queryFn: () => api.getDatasets(params),
  })
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: queryKeys.dataset(id),
    queryFn: () => api.getDataset(id),
    enabled: !!id,
  })
}

export function useExportDataset() {
  return useMutation({
    mutationFn: ({ id, format }: { id: string; format: string }) =>
      api.exportDataset(id, format),
  })
}

// Providers Hooks
export function useProviders() {
  return useQuery({
    queryKey: queryKeys.providers,
    queryFn: () => api.getProviders(),
    refetchInterval: 60000, // Refresh every minute
  })
}

export function useProvider(id: string) {
  return useQuery({
    queryKey: queryKeys.provider(id),
    queryFn: () => api.getProvider(id),
    enabled: !!id,
  })
}

export function useUpdateProvider() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      api.updateProvider(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.provider(id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.providers })
    },
  })
}

export function useProviderMetrics(id: string) {
  return useQuery({
    queryKey: queryKeys.providerMetrics(id),
    queryFn: () => api.getProviderMetrics(id),
    enabled: !!id,
    refetchInterval: 30000,
  })
}

// Metrics Hooks
export function useMetrics() {
  return useQuery({
    queryKey: queryKeys.metrics,
    queryFn: () => api.getMetrics(),
    refetchInterval: 10000, // Refresh every 10 seconds
  })
}

// Health Hooks
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.getHealth(),
    refetchInterval: 30000,
  })
}
