import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : 'An unexpected error occurred.',
    };
  }

  override componentDidCatch(error: unknown, info: unknown) {
    // Log to console in dev; swap for real error tracker in prod
    console.error('[ErrorBoundary]', error, info);
  }

  override render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center bg-[#0F0F1A] px-6">
          <div className="max-w-md w-full rounded-2xl border border-red-500/20 bg-red-900/10 px-8 py-10 text-center">
            <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-red-400" />
            <h1 className="mb-2 text-xl font-semibold text-white">Something went wrong</h1>
            <p className="mb-6 text-sm text-gray-400 leading-relaxed">{this.state.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="btn-secondary"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
