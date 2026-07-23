import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getJobStatus } from "../api/client";
import type { JobStatusResponse } from "../types";

const POLL_INTERVAL_MS = 1500;

interface UseJobPollingResult {
  status: JobStatusResponse | null;
  pollError: string | null;
}

/**
 * Polls GET /jobs/{id} at a fixed interval until the job reaches a terminal
 * stage ("done" or "failed"). Simple polling (rather than WebSockets/SSE)
 * is intentional here: job updates are coarse-grained (a handful of stage
 * transitions), so the added complexity of a persistent connection isn't
 * justified for a local single-user desktop app.
 */
export function useJobPolling(jobId: string | null): UseJobPollingResult {
  const [status, setStatus] = useState<JobStatusResponse | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const poll = useCallback(async (id: string) => {
    try {
      const result = await getJobStatus(id);
      setStatus(result);
      setPollError(null);

      if (result.stage !== "done" && result.stage !== "failed") {
        timerRef.current = window.setTimeout(() => poll(id), POLL_INTERVAL_MS);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Error de conexión";
      setPollError(message);
      timerRef.current = window.setTimeout(() => poll(id), POLL_INTERVAL_MS);
    }
  }, []);

  useEffect(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setStatus(null);
    setPollError(null);

    if (jobId) {
      poll(jobId);
    }

    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, [jobId, poll]);

  return { status, pollError };
}
