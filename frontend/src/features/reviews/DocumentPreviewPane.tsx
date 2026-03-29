import { useEffect, useMemo, useState } from 'react';
import { FileText, Loader2, Search, ZoomIn, ZoomOut } from 'lucide-react';
import type { DocumentPreviewSource } from '@/types/models';

interface DocumentPreviewPaneProps {
  source?: DocumentPreviewSource;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

export function DocumentPreviewPane({
  source,
  isLoading,
  isError,
  onRetry,
}: DocumentPreviewPaneProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    if (!source?.blob) {
      setObjectUrl(null);
      return;
    }

    const url = URL.createObjectURL(source.blob);
    setObjectUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [source]);

  useEffect(() => {
    setZoom(1);
  }, [source?.filename]);

  const kind = useMemo(() => detectPreviewKind(source?.mimeType, source?.filename), [source?.filename, source?.mimeType]);

  return (
    <div className="card p-5 xl:sticky xl:top-8">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-base font-semibold text-white mb-1">Source Document</h3>
          <p className="text-sm text-gray-400 break-all">
            {source?.filename ?? 'Preview loads when the source document is available.'}
          </p>
        </div>

        {source && objectUrl && (
          <div className="flex items-center gap-2">
            {kind === 'image' && (
              <>
                <button
                  type="button"
                  onClick={() => setZoom((current) => Math.max(0.75, Number((current - 0.1).toFixed(2))))}
                  className="btn-ghost"
                  aria-label="Zoom out"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoom((current) => Math.min(2.5, Number((current + 0.1).toFixed(2))))}
                  className="btn-ghost"
                  aria-label="Zoom in"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[#2A2A3E] bg-[#0F0F1A] overflow-hidden min-h-[420px]">
        {isLoading ? (
          <div className="h-[420px] flex items-center justify-center text-gray-400 gap-3">
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading document preview...
          </div>
        ) : isError ? (
          <div className="h-[420px] flex flex-col items-center justify-center text-center px-8">
            <FileText className="w-12 h-12 text-gray-500 mb-4" />
            <p className="text-sm text-gray-300 mb-2">Could not load the source document preview.</p>
            <p className="text-xs text-gray-500 mb-4">
              The review workflow still works, but the original document is temporarily unavailable.
            </p>
            <button type="button" onClick={onRetry} className="btn-secondary">
              Retry preview
            </button>
          </div>
        ) : !source || !objectUrl ? (
          <div className="h-[420px] flex flex-col items-center justify-center text-center px-8">
            <Search className="w-12 h-12 text-gray-500 mb-4" />
            <p className="text-sm text-gray-300 mb-2">No preview available yet.</p>
            <p className="text-xs text-gray-500">
              The source file will appear here when the review case is linked to an uploaded document.
            </p>
          </div>
        ) : kind === 'image' ? (
          <div className="h-[70vh] max-h-[920px] overflow-auto bg-[#0B0B14]">
            <div className="min-h-full flex items-start justify-center p-4">
              <img
                src={objectUrl}
                alt={source.filename}
                className="rounded-lg shadow-[0_18px_60px_rgba(0,0,0,0.35)] origin-top transition-transform duration-200 ease-out"
                style={{ transform: `scale(${zoom})` }}
              />
            </div>
          </div>
        ) : kind === 'pdf' ? (
          <div className="h-[70vh] max-h-[920px] bg-white">
            <iframe
              src={objectUrl}
              title={source.filename}
              className="w-full h-full border-0"
            />
          </div>
        ) : (
          <div className="h-[420px] flex flex-col items-center justify-center text-center px-8">
            <FileText className="w-12 h-12 text-gray-500 mb-4" />
            <p className="text-sm text-gray-300 mb-2">Preview is not available for this file type.</p>
            <p className="text-xs text-gray-500 mb-4">
              This file type is linked to the review case, but inline preview is not available yet.
            </p>
          </div>
        )}
      </div>

      {kind === 'pdf' && source && (
        <p className="text-xs text-gray-500 mt-3">
          PDF preview uses the browser&apos;s built-in viewer for smooth multi-page navigation and zoom controls.
        </p>
      )}
    </div>
  );
}

function detectPreviewKind(mimeType?: string, filename?: string): 'image' | 'pdf' | 'unsupported' {
  const normalizedType = (mimeType ?? '').toLowerCase();
  const normalizedName = (filename ?? '').toLowerCase();

  if (normalizedType.startsWith('image/') || /\.(png|jpe?g|gif|bmp|tiff?)$/.test(normalizedName)) {
    return 'image';
  }

  if (normalizedType.includes('pdf') || normalizedName.endsWith('.pdf')) {
    return 'pdf';
  }

  return 'unsupported';
}
