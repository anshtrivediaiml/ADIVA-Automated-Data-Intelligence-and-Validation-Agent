import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, X, FileText, Loader2, CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api/jobsApi';
import { useToast } from '@/lib/hooks/useToast';
import { UploadStateCard } from '@/components/ui/UploadStateCard';

const ACCEPTED = ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.tiff'];
const MAX_MB = 50;

export default function SingleUploadPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const mutation = useMutation({
    mutationFn: (f: File) => jobsApi.submitSingle(f),
    onSuccess: (job) => {
      setSubmitted(true);
      toast('Document submitted — opening job tracker…', 'success');
      setTimeout(() => navigate(`/jobs/${job.job_id}`), 900);
    },
    onError: () => {
      setError('Upload failed. Please check the file and try again.');
      toast('Upload failed. Please check the file and try again.', 'error');
    },
  });

  function validate(f: File): string | null {
    if (f.size > MAX_MB * 1024 * 1024) return `File too large. Max ${MAX_MB}MB.`;
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED.includes(ext)) return `Unsupported file type. Accepted: ${ACCEPTED.join(', ')}`;
    return null;
  }

  function handleFile(f: File) {
    const err = validate(f);
    if (err) { setError(err); return; }
    setError(null);
    setFile(f);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const submissionValue = submitted ? 'Job created ✓' : mutation.isPending ? 'Submitting' : 'Idle';
  const submissionTone = submitted ? 'green' : mutation.isPending ? 'brand' : 'slate';

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-white mb-1">Upload Document</h2>
        <p className="text-gray-400 text-sm">Submit a single document for AI extraction and validation</p>
      </div>

      <div className="card p-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <UploadStateCard
            icon={<Sparkles className="w-4 h-4" />}
            title="Selection"
            value={file ? 'Ready' : 'Waiting'}
            hint={file ? 'A valid file is selected and ready to submit.' : 'Choose one supported file to begin.'}
            tone={file ? 'brand' : 'slate'}
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
                ? 'Job accepted — redirecting to the tracker now.'
                : mutation.isPending
                ? 'The file is being uploaded and queued for processing.'
                : 'Submission starts after you confirm the upload.'
            }
            tone={submissionTone}
          />
          <UploadStateCard
            icon={error ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
            title="Validation"
            value={error ? 'Needs attention' : file ? 'Valid file' : 'No file yet'}
            hint={error ?? (file ? 'Type and size checks passed.' : 'PDF, image, DOCX, and TIFF are supported.')}
            tone={error ? 'amber' : file ? 'green' : 'slate'}
          />
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => document.getElementById('file-input')?.click()}
          className={`relative flex flex-col items-center justify-center gap-4 border-2 border-dashed rounded-xl p-12 cursor-pointer transition-colors ${
            dragOver
              ? 'border-[#4F46E5] bg-[#4F46E5]/5'
              : 'border-[#2A2A3E] hover:border-[#4F46E5]/50 hover:bg-[#1A1A2E]'
          }`}
        >
          <Upload className={`w-10 h-10 ${dragOver ? 'text-[#4F46E5]' : 'text-gray-500'}`} />
          <div className="text-center">
            <p className="text-white font-medium mb-1">
              {dragOver ? 'Drop to upload' : 'Drag & drop or click to browse'}
            </p>
            <p className="text-gray-500 text-sm">Max {MAX_MB}MB per file</p>
          </div>
          <div className="flex gap-2 flex-wrap justify-center">
            {ACCEPTED.map((ext) => (
              <span key={ext} className="px-2 py-0.5 rounded text-xs bg-[#2A2A3E] text-gray-400 uppercase">
                {ext.slice(1)}
              </span>
            ))}
          </div>
          <input
            id="file-input"
            type="file"
            className="hidden"
            accept={ACCEPTED.join(',')}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
        </div>

        {file && (
          <div className="mt-4 flex items-center gap-3 p-4 bg-[#0F0F1A] rounded-lg border border-[#2A2A3E]">
            <FileText className="w-5 h-5 text-[#4F46E5] flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white font-medium truncate">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setFile(null); setError(null); }}
              className="p-1 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {mutation.isPending && (
          <div className="mt-4 rounded-lg border border-[#4F46E5]/30 bg-[#4F46E5]/10 p-4 text-sm text-[#C7D2FE] flex items-start gap-3">
            <Loader2 className="w-4 h-4 animate-spin mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium text-white mb-1">Submitting document</div>
              <div>The file is being uploaded and a processing job will open automatically once the backend queues it.</div>
            </div>
          </div>
        )}

        {submitted && !mutation.isPending && (
          <div className="mt-4 rounded-lg border border-green-500/30 bg-green-900/20 p-4 text-sm text-green-300 flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-medium text-white mb-1">Job created successfully</div>
              <div>Redirecting you to the job tracker…</div>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 rounded-lg bg-red-900/20 border border-red-800/40 text-sm text-red-400">
            {error}
          </div>
        )}

        <button
          onClick={() => file && mutation.mutate(file)}
          disabled={!file || mutation.isPending || submitted}
          className={`btn-primary w-full mt-6 flex items-center justify-center gap-2 py-3 transition-opacity ${mutation.isPending ? 'opacity-75' : ''}`}
        >
          {submitted ? (
            <><CheckCircle2 className="w-4 h-4" /> Submitted</>
          ) : mutation.isPending ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
          ) : (
            <><Upload className="w-4 h-4" /> Submit for Processing</>
          )}
        </button>
      </div>
    </div>
  );
}
