'use client'

import { useState } from 'react'
import {
  Save,
  RotateCcw,
  History,
  CheckCircle2,
  Clock,
  ArrowRight,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  CheckpointData,
  RestoreCheckpointRequest,
  RestoreCheckpointResponse,
} from '@/lib/api/client'
import { clsx } from 'clsx'

interface CheckpointPanelProps {
  jobId: string
  checkpoints?: CheckpointData[]
  onRestore?: (checkpointId: string) => Promise<RestoreCheckpointResponse>
  onCreateCheckpoint?: () => Promise<CheckpointData>
  isLoading?: boolean
}

const stageColors: Record<string, string> = {
  discovery: 'bg-blue-500',
  extraction: 'bg-green-500',
  filtering: 'bg-yellow-500',
  construction: 'bg-purple-500',
  export: 'bg-orange-500',
  completed: 'bg-emerald-500',
}

const stageLabels: Record<string, string> = {
  discovery: 'Discovery',
  extraction: 'Extraction',
  filtering: 'Filtering',
  construction: 'Construction',
  export: 'Export',
  completed: 'Completed',
}

export function CheckpointPanel({
  jobId,
  checkpoints = [],
  onRestore,
  onCreateCheckpoint,
  isLoading = false,
}: CheckpointPanelProps) {
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<string | null>(null)
  const [restoreResult, setRestoreResult] = useState<RestoreCheckpointResponse | null>(null)
  const [isRestoring, setIsRestoring] = useState(false)
  const [isCreatingCheckpoint, setIsCreatingCheckpoint] = useState(false)

  const handleRestore = async () => {
    if (!selectedCheckpoint || !onRestore) return

    setIsRestoring(true)
    try {
      const request: RestoreCheckpointRequest = {
        job_id: jobId,
        checkpoint_id: selectedCheckpoint,
      }
      const result = await onRestore(selectedCheckpoint)
      setRestoreResult(result)
    } catch (error) {
      console.error('Restore failed:', error)
      setRestoreResult({
        success: false,
        message: 'Failed to restore from checkpoint',
        progress: 0,
        samples_generated: 0,
      })
    } finally {
      setIsRestoring(false)
    }
  }

  const handleCreateCheckpoint = async () => {
    if (!onCreateCheckpoint) return

    setIsCreatingCheckpoint(true)
    try {
      await onCreateCheckpoint()
    } catch (error) {
      console.error('Checkpoint creation failed:', error)
    } finally {
      setIsCreatingCheckpoint(false)
    }
  }

  const latestCheckpoint = checkpoints[0]

  return (
    <div className="space-y-4">
      {/* Header with progress */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                <Save className="h-5 w-5" />
                Checkpoint Management
              </CardTitle>
              <CardDescription>Job: {jobId}</CardDescription>
            </div>
            {latestCheckpoint && (
              <div className="text-right">
                <div className="text-2xl font-bold">
                  {Math.round(latestCheckpoint.progress * 100)}%
                </div>
                <div className="text-sm text-muted-foreground">Current Progress</div>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCreateCheckpoint}
              disabled={isCreatingCheckpoint || !onCreateCheckpoint}
            >
              {isCreatingCheckpoint ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save Checkpoint
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleRestore}
              disabled={!selectedCheckpoint || isRestoring || !onRestore}
            >
              {isRestoring ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RotateCcw className="h-4 w-4 mr-2" />
              )}
              Restore
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Restore Result */}
      {restoreResult && (
        <Card className={restoreResult.success ? 'border-green-500' : 'border-red-500'}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              {restoreResult.success ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-red-500" />
              )}
              <span className={restoreResult.success ? 'text-green-500' : 'text-red-500'}>
                {restoreResult.message}
              </span>
            </div>
            {restoreResult.success && restoreResult.checkpoint && (
              <div className="mt-2 text-sm text-muted-foreground">
                Resuming from: {stageLabels[restoreResult.checkpoint.stage] || restoreResult.checkpoint.stage}
                {' • '}
                {restoreResult.samples_generated} samples generated
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Checkpoint History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <History className="h-4 w-4" />
            Checkpoint History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : checkpoints.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No checkpoints saved yet</p>
            </div>
          ) : (
            <ScrollArea className="h-[300px]">
              <div className="space-y-2">
                {checkpoints.map((checkpoint, index) => (
                  <div
                    key={checkpoint.checkpoint_id}
                    className={clsx(
                      'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                      selectedCheckpoint === checkpoint.checkpoint_id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-muted/50'
                    )}
                    onClick={() => setSelectedCheckpoint(checkpoint.checkpoint_id)}
                  >
                    <div className={clsx(
                      'w-2 h-2 rounded-full',
                      index === 0 ? 'bg-green-500' : 'bg-muted-foreground'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className={stageColors[checkpoint.stage]}>
                          {stageLabels[checkpoint.stage] || checkpoint.stage}
                        </Badge>
                        <span className="text-sm font-medium">
                          {Math.round(checkpoint.progress * 100)}%
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {checkpoint.samples_generated} samples •{' '}
                        {new Date(checkpoint.created_at).toLocaleString()}
                      </div>
                    </div>
                    {checkpoint.provider_context && (
                      <div className="text-xs text-muted-foreground">
                        {checkpoint.provider_context.provider_name}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

interface CheckpointTimelineProps {
  checkpoints: CheckpointData[]
  currentStage?: string
}

export function CheckpointTimeline({ checkpoints, currentStage }: CheckpointTimelineProps) {
  const stages = ['discovery', 'extraction', 'filtering', 'construction', 'export', 'completed']

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-2">
      {stages.map((stage, index) => {
        const checkpoint = checkpoints.find(cp => cp.stage === stage)
        const isCompleted = checkpoint && checkpoint.progress >= 1
        const isCurrent = currentStage === stage

        return (
          <div key={stage} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={clsx(
                'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium',
                isCompleted
                  ? 'bg-green-500 text-white'
                  : isCurrent
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
              )}>
                {isCompleted ? <CheckCircle2 className="h-4 w-4" /> : index + 1}
              </div>
              <span className="text-xs mt-1 text-muted-foreground">
                {stageLabels[stage]}
              </span>
              {checkpoint && (
                <span className="text-xs text-muted-foreground">
                  {Math.round(checkpoint.progress * 100)}%
                </span>
              )}
            </div>
            {index < stages.length - 1 && (
              <ArrowRight className="h-4 w-4 mx-2 text-muted-foreground" />
            )}
          </div>
        )
      })}
    </div>
  )
}