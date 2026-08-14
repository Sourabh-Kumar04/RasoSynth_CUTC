'use client'

import { useState } from 'react'
import {
  Settings,
  User,
  Shield,
  Key,
  Database,
  Server,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('general')

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Platform configuration and environment settings
        </p>
      </div>

      {/* Info Notice */}
      <Card className="border-info/50 bg-info/5">
        <CardContent className="p-4 flex items-start gap-3">
          <Settings className="h-5 w-5 text-info mt-0.5" />
          <div>
            <p className="text-sm font-medium">Configuration via Environment</p>
            <p className="text-xs text-muted-foreground mt-1">
              Platform settings are managed through environment variables in the .env file.
              Changes require restarting the application.
            </p>
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="limits">Limits</TabsTrigger>
        </TabsList>

        {/* General Settings */}
        <TabsContent value="general" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">General Configuration</CardTitle>
              <CardDescription>
                Core platform settings loaded from environment
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Server className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Demo Mode</p>
                      <p className="text-xs text-muted-foreground">
                        Enable simulated dataset generation without API calls
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline">DEMO_MODE in .env</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Database className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">PostgreSQL Database</p>
                      <p className="text-xs text-muted-foreground">
                        Connection: postgresql+asyncpg://dataset_user:***@postgres:5432/dataset_engine
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline">POSTGRES_URL in .env</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Key className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Redis Cache</p>
                      <p className="text-xs text-muted-foreground">
                        Connection: redis://redis:6379/0
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline">REDIS_URL in .env</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Provider Settings */}
        <TabsContent value="providers" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Provider API Keys</CardTitle>
              <CardDescription>
                Configure API keys for AI providers
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded bg-blue-500/10 flex items-center justify-center text-blue-500 font-bold">
                      G
                    </div>
                    <div>
                      <p className="font-medium">Google Gemini</p>
                      <p className="text-xs text-muted-foreground">GOOGLE_API_KEY in .env</p>
                    </div>
                  </div>
                  <Badge variant="outline">Environment</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded bg-green-500/10 flex items-center justify-center text-green-500 font-bold">
                      N
                    </div>
                    <div>
                      <p className="font-medium">NVIDIA NIM</p>
                      <p className="text-xs text-muted-foreground">NVIDIA_API_KEY in .env</p>
                    </div>
                  </div>
                  <Badge variant="outline">Environment</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded bg-orange-500/10 flex items-center justify-center text-orange-500 font-bold">
                      A
                    </div>
                    <div>
                      <p className="font-medium">Anthropic Claude</p>
                      <p className="text-xs text-muted-foreground">ANTHROPIC_API_KEY in .env</p>
                    </div>
                  </div>
                  <Badge variant="outline">Environment</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded bg-gray-500/10 flex items-center justify-center text-gray-500 font-bold">
                      O
                    </div>
                    <div>
                      <p className="font-medium">OpenAI</p>
                      <p className="text-xs text-muted-foreground">OPENAI_API_KEY in .env</p>
                    </div>
                  </div>
                  <Badge variant="outline">Environment</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded bg-purple-500/10 flex items-center justify-center text-purple-500 font-bold">
                      H
                    </div>
                    <div>
                      <p className="font-medium">Hugging Face</p>
                      <p className="text-xs text-muted-foreground">HF_TOKEN in .env</p>
                    </div>
                  </div>
                  <Badge variant="outline">Environment</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Settings */}
        <TabsContent value="security" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Security Configuration</CardTitle>
              <CardDescription>
                Authentication and authorization settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Shield className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">JWT Authentication</p>
                      <p className="text-xs text-muted-foreground">
                        Token-based authentication with JWT_SECRET
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline">JWT_SECRET in .env</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <User className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Authentication Mode</p>
                      <p className="text-xs text-muted-foreground">
                        Set AUTH_DISABLED=true to disable authentication
                      </p>
                    </div>
                  </div>
                  <Badge variant="outline">AUTH_DISABLED in .env</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Limits Settings */}
        <TabsContent value="limits" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Resource Limits</CardTitle>
              <CardDescription>
                Rate limits and resource constraints
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Max Concurrent Jobs</p>
                    <p className="text-xs text-muted-foreground">
                      Maximum number of simultaneous dataset generation jobs
                    </p>
                  </div>
                  <Badge variant="outline">MAX_CONCURRENT_JOBS in .env</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Token Budget (USD)</p>
                    <p className="text-xs text-muted-foreground">
                      Total budget for API tokens across all providers
                    </p>
                  </div>
                  <Badge variant="outline">TOKEN_BUDGET_USD in .env</Badge>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Rate Limits</p>
                    <p className="text-xs text-muted-foreground">
                      Per-provider rate limits (requests per minute)
                    </p>
                  </div>
                  <Badge variant="outline">RATE_LIMIT_* in .env</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* How to Modify */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">How to Modify Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>1. Edit the <code className="bg-surface px-1 rounded">.env</code> file in the project root</p>
            <p>2. Update the desired environment variables</p>
            <p>3. Restart the application for changes to take effect</p>
            <p className="mt-4">
              See <code className="bg-surface px-1 rounded">.env.example</code> for all available options.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}