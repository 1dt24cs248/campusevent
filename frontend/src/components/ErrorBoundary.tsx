import React, { Component } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex items-center justify-center min-h-[300px] p-8">
          <div className="card p-8 max-w-md w-full text-center">
            <div className="w-16 h-16 rounded-full bg-red-900/40 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={28} className="text-red-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Something went wrong</h3>
            <p className="text-sm text-slate-400 mb-2">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <p className="text-xs text-slate-600 mb-6 font-mono bg-slate-800 p-2 rounded">
              {this.state.error?.name}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="btn-primary flex items-center gap-2 mx-auto"
            >
              <RefreshCw size={16} />
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
