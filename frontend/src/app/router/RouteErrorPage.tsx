import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

export function RouteErrorPage() {
  const error = useRouteError();

  const title = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText || 'Request failed'}`
    : 'Something went wrong';

  const message = isRouteErrorResponse(error)
    ? typeof error.data === 'string'
      ? error.data
      : 'The requested page could not be loaded.'
    : error instanceof Error
      ? error.message
      : 'An unexpected routing error occurred.';

  return (
    <div className="min-h-screen bg-[#0F0F1A] flex items-center justify-center p-8">
      <div className="card max-w-xl w-full p-8 text-center">
        <AlertTriangle className="w-14 h-14 text-amber-400 mx-auto mb-4" />
        <h1 className="text-2xl font-semibold text-white mb-2">{title}</h1>
        <p className="text-sm text-gray-400 mb-6">{message}</p>
        <div className="flex items-center justify-center gap-3">
          <button type="button" onClick={() => window.location.reload()} className="btn-secondary inline-flex items-center gap-2">
            <RefreshCcw className="w-4 h-4" />
            Reload
          </button>
          <Link to="/dashboard" className="btn-primary">
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
