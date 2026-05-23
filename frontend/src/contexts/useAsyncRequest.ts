import { useCallback, useRef } from "react";

export const useLatestAsyncRequest = () => {
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const nextRequest = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    const isStale = () => requestId !== requestIdRef.current || controller.signal.aborted;
    return { requestId, controller, signal: controller.signal, isStale };
  }, []);

  const invalidate = useCallback(() => {
    requestIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { nextRequest, invalidate };
};
