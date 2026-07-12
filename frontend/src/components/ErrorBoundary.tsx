import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  /** Rendered in place of the children after a render error. */
  fallback: ReactNode;
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
};

/**
 * Catches render errors so one broken section doesn't blank the whole app.
 * Class component because React only exposes error boundaries that way.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Render error caught by boundary:", error, errorInfo.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

/** Compact in-flow fallback for one section of the page. */
export const SectionErrorFallback: React.FC = () => (
  <div
    role="alert"
    className="panel-shell flex min-h-[10rem] items-center justify-center p-6 text-center text-sm text-muted-foreground"
  >
    This section failed to load. Reload the page to try again.
  </div>
);
