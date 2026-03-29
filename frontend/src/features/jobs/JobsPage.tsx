import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Download, Eye, FileText, RefreshCw, Search, SlidersHorizontal, Trash2 } from 'lucide-react';
import { jobsApi } from '@/lib/api/jobsApi';
import { Pagination } from '@/components/ui/Pagination';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { StatusPill } from '@/components/ui/StatusPill';
import { clampPage, formatDate, isTerminalStatus, paginateItems } from '@/lib/utils';
import type { Job, JobStatus } from '@/types/models';

const PAGE_SIZE = 15;
type StatusFilter = JobStatus | 'all';

export default function JobsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState(1);
  const [jobPendingDelete, setJobPendingDelete] = useState<Job | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const apiStatusFilter =
    statusFilter === 'all' || statusFilter === 'processing' ? undefined : statusFilter;

  const { data, isLoading, isError, refetch, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['jobs', 'list', apiStatusFilter ?? 'all'],
    queryFn: () => jobsApi.list({ limit: 200, status: apiStatusFilter }),
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.remove(jobId),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
      queryClient.invalidateQueries({ queryKey: ['result'] });
      queryClient.invalidateQueries({ queryKey: ['recovery'] });
    },
  });

  const jobs: Job[] = data ?? [];
  const hasLoadedData = jobs.length > 0;
  const showInitialLoading = isLoading && !hasLoadedData;
  const showHardError = isError && !hasLoadedData;
  const lastSyncedAt = dataUpdatedAt ? formatDate(new Date(dataUpdatedAt).toISOString()) : null;

  const filteredJobs = useMemo(() => {
    const query = search.trim().toLowerCase();
    return jobs.filter((job) => {
      const matchesSearch =
        !query ||
        (job.file_name ?? '').toLowerCase().includes(query) ||
        (job.doc_type ?? '').toLowerCase().includes(query) ||
        job.job_id.toLowerCase().includes(query);
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'processing'
          ? job.status === 'processing' || job.status === 'queued'
          : job.status === statusFilter);
      return matchesSearch && matchesStatus;
    });
  }, [jobs, search, statusFilter]);

  const paginatedJobs = paginateItems(filteredJobs, page, PAGE_SIZE);

  useEffect(() => {
    setPage((currentPage) => clampPage(currentPage, filteredJobs.length, PAGE_SIZE));
  }, [filteredJobs.length]);

  const activeCount = jobs.filter((job) => !isTerminalStatus(job.status)).length;
  const completedCount = jobs.filter((job) => job.status === 'completed').length;
  const reviewCount = jobs.filter((job) => job.status === 'needs_review').length;
  const failedCount = jobs.filter((job) => job.status === 'failed').length;

  const handleDelete = (job: Job) => {
    setJobPendingDelete(job);
  };

  const confirmDelete = () => {
    if (!jobPendingDelete || deleteMutation.isPending) {
      return;
    }
    deleteMutation.mutate(jobPendingDelete.job_id, {
      onSuccess: () => {
        setJobPendingDelete(null);
      },
    });
  };

  return (
    <div className="p-8">
      <ConfirmDialog
        open={!!jobPendingDelete}
        title="Delete job?"
        description={`Delete the job for "${jobPendingDelete?.file_name ?? jobPendingDelete?.job_id ?? ''}"? This removes the job, its outputs, and any linked review data permanently.`}
        confirmLabel={deleteMutation.isPending ? 'Deleting...' : 'Delete Job'}
        cancelLabel="Keep Job"
        tone="danger"
        busy={deleteMutation.isPending}
        onCancel={() => setJobPendingDelete(null)}
        onConfirm={confirmDelete}
      />

      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white mb-1">Jobs</h2>
          <p className="text-gray-400 text-sm">Operational workspace for all submitted processing jobs</p>
        </div>
        <button onClick={() => refetch()} className="btn-secondary text-sm inline-flex items-center gap-2">
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <SummaryCard
          label="All Jobs"
          value={jobs.length}
          tone="slate"
          active={statusFilter === 'all'}
          onClick={() => setStatusFilter('all')}
        />
        <SummaryCard
          label="Active"
          value={activeCount}
          tone="blue"
          active={statusFilter === 'queued' || statusFilter === 'processing'}
          onClick={() =>
            setStatusFilter((current) =>
              current === 'processing' || current === 'queued' ? 'all' : 'processing',
            )
          }
        />
        <SummaryCard
          label="Needs Review"
          value={reviewCount}
          tone="amber"
          active={statusFilter === 'needs_review'}
          onClick={() => setStatusFilter((current) => (current === 'needs_review' ? 'all' : 'needs_review'))}
        />
        <SummaryCard
          label="Completed"
          value={completedCount}
          tone="green"
          secondary={`Failed: ${failedCount}`}
          active={statusFilter === 'completed'}
          onClick={() => setStatusFilter((current) => (current === 'completed' ? 'all' : 'completed'))}
        />
      </div>

      <div className="card mb-6">
        <div className="p-6 border-b border-[#2A2A3E]">
          <div className="flex items-center gap-2 mb-4">
            <SlidersHorizontal className="w-4 h-4 text-gray-500" />
            <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">Filters</h3>
          </div>

          <div className="grid grid-cols-[minmax(0,1.4fr)_220px] gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by file name, job ID, or document type..."
                className="input-base pl-10"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              className="input-base cursor-pointer"
            >
              <option value="all">All status</option>
              <option value="queued">Queued</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="needs_review">Needs Review</option>
              <option value="low_confidence">Low Confidence</option>
                <option value="failed">Failed</option>
              </select>
          </div>

          {(search || statusFilter !== 'all') && (
            <div className="mt-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <span className="px-2 py-0.5 rounded-full bg-[#4F46E5]/10 text-[#A5B4FC] border border-[#4F46E5]/20 font-medium">
                  {filteredJobs.length} matches
                </span>
                <span className="text-gray-500">out of {jobs.length} total jobs</span>
              </div>
              <button
                onClick={() => {
                  setSearch('');
                  setStatusFilter('all');
                }}
                className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        {showInitialLoading ? (
          <TableSkeleton />
        ) : showHardError ? (
          <EmptyState
            icon={<FileText className="w-12 h-12 opacity-30" />}
            message="Failed to load jobs."
            actionLabel="Retry"
            onAction={() => refetch()}
          />
        ) : jobs.length === 0 ? (
          <EmptyState
            icon={<FileText className="w-12 h-12 opacity-30" />}
            message="No jobs yet. Upload a document to get started."
            actionLabel="Upload Document"
            actionTo="/upload"
          />
        ) : filteredJobs.length === 0 ? (
          <EmptyState
            icon={<Search className="w-12 h-12 opacity-30" />}
            message="No jobs match your current filters."
            actionLabel="Clear Filters"
            onAction={() => {
              setSearch('');
              setStatusFilter('all');
            }}
          />
        ) : (
          <>
            <div className="px-6 py-4 border-b border-[#2A2A3E] flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Job History</h3>
                <p className="text-sm text-gray-400">Track status, review requirements, and results from one place</p>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-500">
                <span>{filteredJobs.length} visible jobs</span>
                {lastSyncedAt ? <span className="text-gray-600">Last synced {lastSyncedAt}</span> : null}
                {isFetching && !isLoading ? (
                  <span className="inline-flex items-center gap-2 text-[#A5B4FC]">
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Syncing
                  </span>
                ) : null}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="sticky top-0 z-10">
                  <tr className="border-b border-[#2A2A3E] bg-[#0F0F1A]/95 backdrop-blur-md">
                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Job ID</th>
                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">File Name</th>
                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Type</th>
                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                    <th className="text-right px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Confidence</th>
                    <th className="text-left px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Submitted</th>
                    <th className="text-right px-6 py-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2A2A3E]">
                  {paginatedJobs.map((job) => (
                    <tr
                      key={job.job_id}
                      onClick={() => navigate(`/jobs/${job.job_id}`)}
                      className="group cursor-pointer border-l-2 border-transparent hover:border-[#4F46E5] hover:bg-[#1F1F2E]/40 transition-all"
                    >
                      <td className="px-6 py-4 text-sm font-mono text-gray-500 group-hover:text-[#A5B4FC] transition-colors">
                        {job.job_id.slice(0, 8)}
                      </td>
                      <td className="px-6 py-4 text-sm text-white font-medium max-w-[280px] truncate" title={job.file_name ?? undefined}>
                        {job.file_name ?? '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-400">{job.doc_type ?? '-'}</td>
                      <td className="px-6 py-4 text-sm"><StatusPill status={job.status} /></td>
                      <td className="px-6 py-4 text-sm text-right font-mono text-gray-300">
                        {job.overall_conf != null ? (
                          <span className={job.overall_conf >= 0.9 ? 'text-green-400' : job.overall_conf >= 0.7 ? 'text-amber-400' : 'text-red-400'}>
                            {(job.overall_conf * 100).toFixed(1)}%
                          </span>
                        ) : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-400">{formatDate(job.submitted_at)}</td>
                      <td className="px-6 py-4 text-sm text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex justify-end gap-1">
                          <Link
                            to={`/jobs/${job.job_id}`}
                            className="rounded p-2 text-gray-400 transition-colors hover:bg-[#2A2A3E] hover:text-white"
                            title="Track Job"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          {['completed', 'needs_review', 'low_confidence'].includes(job.status) && (
                            <Link
                              to={`/jobs/${job.job_id}/result`}
                              className="rounded p-2 text-[#A5B4FC] bg-[#4F46E5]/10 border border-[#4F46E5]/20 transition-all hover:bg-[#4F46E5] hover:text-white shadow-sm"
                              title="View Result"
                            >
                              <Download className="w-4 h-4" />
                            </Link>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDelete(job)}
                            disabled={deleteMutation.isPending}
                            className="rounded p-2 text-red-300 transition-colors hover:bg-red-500/10 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-50"
                            title="Delete Job"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} totalItems={filteredJobs.length} onPageChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone,
  secondary,
  active = false,
  onClick,
}: {
  label: string;
  value: string | number;
  tone: 'slate' | 'blue' | 'amber' | 'green';
  secondary?: string;
  active?: boolean;
  onClick: () => void;
}) {
  const tones: Record<string, string> = {
    slate: 'text-gray-200',
    blue: 'text-blue-400',
    amber: 'text-amber-400',
    green: 'text-green-400',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`card w-full p-5 text-left transition-all ${
        active
          ? 'border-[#4F46E5]/60 shadow-[0_0_0_1px_rgba(79,70,229,0.2)]'
          : 'hover:border-[#4F46E5]/25'
      }`}
    >
      <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">{label}</div>
      <div className={`text-2xl font-semibold ${tones[tone]}`}>{value}</div>
      {secondary ? <div className="text-xs text-gray-500 mt-1">{secondary}</div> : null}
    </button>
  );
}

function TableSkeleton() {
  return (
    <div className="p-6 space-y-3">
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="h-12 bg-[#0F0F1A] rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

function EmptyState({
  icon,
  message,
  actionLabel,
  onAction,
  actionTo,
}: {
  icon: ReactNode;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  actionTo?: string;
}) {
  return (
    <div className="py-16 text-center flex flex-col items-center gap-3 text-gray-500">
      {icon}
      <p className="text-sm">{message}</p>
      {actionLabel && actionTo ? (
        <Link to={actionTo} className="btn-primary text-sm mt-1">
          {actionLabel}
        </Link>
      ) : null}
      {actionLabel && onAction ? (
        <button onClick={onAction} className="btn-secondary text-sm mt-1">
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
