'use client'

import { useState } from 'react'
import { validateInput } from '@/lib/api/client'
import {
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

interface ValidationFeedbackProps {
  className?: string
}

export function ValidationFeedback({ className }: ValidationFeedbackProps) {
  const [inputValue, setInputValue] = useState('')
  const [validationResult, setValidationResult] = useState<{
    valid: boolean
    error?: string
  } | null>(null)

  const handleValidate = () => {
    const result = validateInput(inputValue)
    setValidationResult(result)
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Shield className="h-5 w-5" />
          Input Validation
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Test Input</label>
            <Textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Enter text to validate..."
              className="min-h-[80px]"
            />
          </div>

          <Button onClick={handleValidate} className="w-full">
            Validate Input
          </Button>

          {validationResult && (
            <div
              className={`p-3 rounded-lg flex items-start gap-2 ${
                validationResult.valid
                  ? 'bg-green-500/10 border border-green-500/20'
                  : 'bg-red-500/10 border border-red-500/20'
              }`}
            >
              {validationResult.valid ? (
                <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5" />
              )}
              <div>
                <p className={`font-medium ${validationResult.valid ? 'text-green-500' : 'text-red-500'}`}>
                  {validationResult.valid ? 'Valid Input' : 'Invalid Input'}
                </p>
                {validationResult.error && (
                  <p className="text-sm text-muted-foreground">{validationResult.error}</p>
                )}
              </div>
            </div>
          )}

          <div className="text-xs text-muted-foreground space-y-1">
            <p>Checks for:</p>
            <ul className="list-disc list-inside">
              <li>Prompt injection patterns</li>
              <li>Template injection ({"{"}{"}"}, [{"["}{"]"}])</li>
              <li>XSS vectors (script tags, javascript:)</li>
              <li>SQL injection patterns</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface ValidationIndicatorProps {
  errors?: string[]
  warnings?: string[]
}

export function ValidationIndicator({ errors, warnings }: ValidationIndicatorProps) {
  if (!errors?.length && !warnings?.length) {
    return (
      <div className="flex items-center gap-1 text-green-500">
        <ShieldCheck className="h-4 w-4" />
        <span className="text-sm">Validated</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1 text-yellow-500">
      <ShieldAlert className="h-4 w-4" />
      <span className="text-sm">
        {errors?.length || 0} errors, {warnings?.length || 0} warnings
      </span>
    </div>
  )
}