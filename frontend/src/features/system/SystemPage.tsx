import { useQuery } from '@tanstack/react-query';
import { XCircle, Clock } from 'lucide-react';
import { healthApi } from '@/lib/api/healthApi';
import type { HealthResponse, SystemStatusResponse } from '@/types/models';

export default function SystemPage() {
  const { data: health, isLoading, isError, dataUpdatedAt, refetch } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: () => healthApi.health(),
    refetchInterval: 30_000,
  });

  const { data: status } = useQuery<SystemStatusResponse>({
    queryKey: ['status'],
    queryFn: () => healthApi.status(),
    refetchInterval: 30_000,
  });

  const overallStatus = normalizeHealthStatus(health?.status ?? status?.readiness ?? 'unknown');
  const dependencyRows = Object.entries(status?.dependencies ?? {});

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white mb-1">System Health</h2>
          <p className="text-gray-400 text-sm">Real-time status of all ADIVA services</p>
        </div>
        <button onClick={() => refetch()} className="btn-secondary text-sm">Refresh</button>
      </div>

      {/* Overall badge */}
      <div className="card p-6 mb-6 flex items-center gap-4">
        <HealthDot status={overallStatus} size="lg" />
        <div>
          <div className="text-xl font-semibold text-white capitalize">
            {isLoading ? 'Checking...' : isError ? 'Unavailable' : overallStatus}
          </div>
          <div className="text-sm text-gray-400 flex items-center gap-1.5 mt-0.5">
            <Clock className="w-3.5 h-3.5" />
            Last updated: {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '-'}
          </div>
        </div>
      </div>

      {/* Services */}
      {dependencyRows.length > 0 && (
        <div className="card mb-6">
          <div className="p-5 border-b border-[#2A2A3E]">
            <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Services</h3>
          </div>
          <div className="divide-y divide-[#2A2A3E]">
            {dependencyRows.map(([name, dependency]) => (
              <div key={name} className="flex items-center justify-between px-6 py-4">
                <div className="flex items-center gap-3">
                  <HealthDot status={normalizeHealthStatus(dependency.status ?? 'unknown')} />
                  <div>
                    <p className="text-sm font-medium text-white capitalize">{name.replace(/_/g, ' ')}</p>
                    {dependency.error && <p className="text-xs text-red-400 mt-0.5">{dependency.error}</p>}
                    {dependency.detail && <p className="text-xs text-gray-500 mt-0.5">{dependency.detail}</p>}
                  </div>
                </div>
                <div className="text-right text-xs text-gray-400">
                  {dependency.latency_ms != null ? <span>{dependency.latency_ms}ms</span> : <span>-</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw Status */}
      {status && (
        <div className="card">
          <div className="p-5 border-b border-[#2A2A3E]">
            <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Status Detail</h3>
          </div>
          <div className="p-5">
            <pre className="text-xs text-gray-300 overflow-auto max-h-64 bg-[#0F0F1A] rounded-lg p-4">
              {JSON.stringify(status, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {(isLoading || isError) && !health && (
        <div className="card p-12 text-center text-gray-500">
          {isLoading ? (
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-[#4F46E5] border-t-transparent animate-spin" />
              <span className="text-sm">Checking services...</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <XCircle className="w-10 h-10 text-red-400" />
              <span className="text-sm">Cannot reach backend. Is the server running on port 8000?</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HealthDot({ status, size = 'sm' }: { status: string; size?: 'sm' | 'lg' }) {
  const sz = size === 'lg' ? 'w-5 h-5' : 'w-3 h-3';
  if (status === 'healthy')  return <div className={`${sz} rounded-full bg-green-500 flex-shrink-0 shadow-[0_0_8px_rgba(34,197,94,0.5)]`} />;
  if (status === 'degraded') return <div className={`${sz} rounded-full bg-amber-500 flex-shrink-0 animate-pulse`} />;
  return <div className={`${sz} rounded-full bg-red-500 flex-shrink-0`} />;
}

function normalizeHealthStatus(status: string): 'healthy' | 'degraded' | 'down' {
  if (status === 'healthy' || status === 'ready' || status === 'available' || status === 'up') return 'healthy';
  if (status === 'degraded' || status === 'warning') return 'degraded';
  return 'down';
}
