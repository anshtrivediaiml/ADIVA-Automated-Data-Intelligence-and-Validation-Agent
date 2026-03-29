import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, X, FileText, Loader2, Layers, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api/jobsApi';
import { useToast } from '@/lib/hooks/useToast';
import { UploadStateCard } from '@/components/ui/UploadStateCard';

const ACCEPTED = ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.tiff'];
const MAX_MB = 50;
const MAX_FILES = 20;

export default function BatchUploadPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [files, setFiles]       = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const mutation = useMutation({
    mutationFn: (fs: File[]) => jobsApi.submitBatch(fs),
    onSuccess: (jobs) => {
      setSubmitted(true);
      toast(`Batch accepted — ${jobs.length} job${jobs.length !== 1 ? 's' : ''} queued`, 'success');
      setTimeout(() => {
        if (jobs.length > 0) navigate('/jobs');
        else navigate('/jobs');
      }, 1000);
    },
    onError: () => {
      setError('Batch upload failed. Please try again.');
      toast('Batch upload failed. Please try again.', 'error');
    },
  });

  function validate(f: File): string | null {
    if (f.size > MAX_MB * 1024 * 1024) return `${f.name} exceeds ${MAX_MB}MB`;
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED.includes(ext)) return `${f.name}: unsupported type`;
    return null;
  }

  function addFiles(incoming: File[]) {
    const next = [...files, ...incoming].slice(0, MAX_FILES);
    const errs = next.map(validate).filter(Boolean) as string[];
    if (errs.length) { setError(errs[0]); return; }
    setError(null);
    setFiles(next);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(Array.from(e.dataTransfer.files));
  }, [files]);

  function removeFile(idx: number) {
    if (mutation.isPending) return;
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  function getFileExt(f: File) {
    return (f.name.split('.').pop() ?? '').toUpperCase();
  }

  function getFileBadge(idx: number) {
    if (submitted) return { label: 'Done ✓', cls: 'bg-green-900/30 text-green-300' };
    if (mutation.isPending) {
      return { label: 'Queued…', cls: 'bg-[#4F46E5]/20 text-[#C7D2FE] animate-pulse' };
    }
    return { label: 'Ready', cls: 'bg-[#1A1A2E] text-gray-400' };
  }

  const submissionValue = submitted ? `${files.length} jobs queued ✓` : mutation.isPending ? 'Submitting' : 'Idle';
  const submissionTone = submitted ? 'green' : mutation.isPending ? 'brand' : 'slate';

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-white mb-1">Batch Upload</h2>
        <p className="text-gray-400 text-sm">Submit up to {MAX_FILES} documents at once</p>
      </div>

      <div className="card p-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <UploadStateCard
            icon={<Layers className="w-4 h-4" />}
            title="Selection"
            value={`${files.length}/${MAX_FILES}`}
            hint={files.length > 0 ? 'Files are staged and ready for batch submission.' : 'Add up to 20 supported files.'}
            tone={files.length > 0 ? 'brand' : 'slate'}
          />
          <UploadStateCard
            icon={
              submitted
                ? <CheckCircle2 className="w-4 h-4" />
                : <Loader2 className={`w-4 h-4 ${mutation.isPending ? 'animate-spin' : ''}`} />
            }
            title="Submission"
            value={submissionValue}
            hint={
              submitted
                ? 'All jobs accepted — navigating to the Jobs workspace.'
                : mutation.isPending
                ? 'The batch is being uploaded and queued.'
                : 'Batch submission begins after you confirm.'
            }
            tone={submissionTone}
          />
          <UploadStateCard
            icon={error ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
            title="Validation"
            value={error ? 'Needs attention' : files.length > 0 ? 'Batch valid' : 'No files yet'}
            hint={error ?? (files.length > 0 ? 'All selected files currently satisfy type and size limits.' : 'Each file must be 50MB or smaller.')}
            tone={error ? 'amber' : files.length > 0 ? 'green' : 'slate'}
          />
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => !mutation.isPending && document.getElementById('batch-input')?.click()}
          className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-10 cursor-pointer transition-colors mb-6 ${
            mutation.isPending ? 'opacity-60 cursor-not-allowed' :
            dragOver ? 'border-[#4F46E5] bg-[#4F46E5]/5' : 'border-[#2A2A3E] hover:border-[#4F46E5]/50'
          }`}
        >
          <Layers className={`w-10 h-10 ${dragOver ? 'text-[#4F46E5]' : 'text-gray-500'}`} />
          <p className="text-white font-medium">Drop multiple files or click to browse</p>
          <p className="text-gray-500 text-sm">{files.length}/{MAX_FILES} files selected</p>
          <input
            id="batch-input"
            type="file"
            multiple
            className="hidden"
            accept={ACCEPTED.join(',')}
            onChange={(e) => addFiles(Array.from(e.target.files ?? []))}
          />
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="space-y-2 mb-6 max-h-64 overflow-y-auto">
            {files.map((f, idx) => {
              const badge = getFileBadge(idx);
              return (
                <div key={idx} className="flex items-center gap-3 p-3 bg-[#0F0F1A] rounded-lg border border-[#2A2A3E]">
                  <FileText className="w-4 h-4 text-[#4F46E5] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{f.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-[#2A2A3E] text-gray-400 uppercase font-medium">
                        {getFileExt(f)}
                      </span>
                      <p className="text-xs text-gray-500">{(f.size / 1024 / 1024).toFixed(2)} MB</p>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => removeFile(idx)}
                    disabled={mutation.isPending}
                    className="p-1 text-gray-500 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Progress bar during upload */}
        {mutation.isPending && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
              <span>Uploading {files.length} file{files.length !== 1 ? 's' : ''}…</span>
            </div>
            <div className="h-1.5 rounded-full bg-[#2A2A3E] overflow-hidden">
              <div className="h-full bg-[#4F46E5] rounded-full animate-pulse w-4/5" />
            </div>
          </div>
        )}

        {/* Success banner */}
        {submitted && !mutation.isPending && (
          <div className="mb-4 rounded-lg border border-green-500/30 bg-green-900/20 p-4 text-sm text-green-300 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium text-white mb-1">Batch accepted</div>
              <div>{files.length} job{files.length !== 1 ? 's' : ''} queued — navigating to Jobs workspace…</div>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-900/20 border border-red-800/40 text-sm text-red-400">{error}</div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => files.length > 0 && mutation.mutate(files)}
            disabled={files.length === 0 || mutation.isPending || submitted}
            className={`btn-primary flex-1 flex items-center justify-center gap-2 py-3 ${mutation.isPending ? 'opacity-75' : ''}`}
          >
            {submitted ? (
              <><CheckCircle2 className="w-4 h-4" /> Submitted</>
            ) : mutation.isPending ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Uploading {files.length} files…</>
            ) : (
              <><Upload className="w-4 h-4" /> Submit {files.length > 0 ? `${files.length} files` : 'files'}</>
            )}
          </button>
          {files.length > 0 && !mutation.isPending && !submitted && (
            <button onClick={() => setFiles([])} className="btn-secondary px-4">
              Clear All
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
