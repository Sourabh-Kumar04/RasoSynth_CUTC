import { create } from 'zustand'
import type { Job, JobStatus } from '@/types/api'

interface JobsState {
  jobs: Job[]
  activeJob: Job | null
  setJobs: (jobs: Job[]) => void
  addJob: (job: Job) => void
  updateJob: (id: string, updates: Partial<Job>) => void
  removeJob: (id: string) => void
  setActiveJob: (job: Job | null) => void
}

export const useJobsStore = create<JobsState>((set) => ({
  jobs: [],
  activeJob: null,

  setJobs: (jobs) => set({ jobs }),

  addJob: (job) => set((state) => ({
    jobs: [job, ...state.jobs]
  })),

  updateJob: (id, updates) => set((state) => ({
    jobs: state.jobs.map((job) =>
      job.id === id ? { ...job, ...updates } : job
    ),
    activeJob: state.activeJob?.id === id
      ? { ...state.activeJob, ...updates }
      : state.activeJob,
  })),

  removeJob: (id) => set((state) => ({
    jobs: state.jobs.filter((job) => job.id !== id),
    activeJob: state.activeJob?.id === id ? null : state.activeJob,
  })),

  setActiveJob: (job) => set({ activeJob: job }),
}))
