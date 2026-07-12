import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/Toaster";
import { AppProvider } from "@/contexts/AppContext";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

const AppCrashFallback = () => (
  <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background p-6 text-center">
    <p className="text-lg font-semibold text-foreground">Something went wrong.</p>
    <p className="text-sm text-muted-foreground">An unexpected error broke this page.</p>
    <button
      type="button"
      onClick={() => window.location.reload()}
      className="rounded-md border border-border bg-card px-4 py-2 text-sm text-foreground hover:bg-muted"
    >
      Reload page
    </button>
  </div>
);

const App = () => (
  <ErrorBoundary fallback={<AppCrashFallback />}>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AppProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/stations/:stationId" element={<Index />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AppProvider>
      </ToastProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;

