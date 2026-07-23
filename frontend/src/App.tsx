import { useEffect, useState } from "react";
import { ApiError, checkBackendHealth, createJob, getDownloadUrl } from "./api/client";
import { ErrorBanner } from "./components/ErrorBanner";
import { ProgressBar } from "./components/ProgressBar";
import { StageIndicator } from "./components/StageIndicator";
import { UrlForm } from "./components/UrlForm";
import { useJobPolling } from "./hooks/useJobPolling";
import type { GenerateRequest } from "./types";

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  const { status, pollError } = useJobPolling(jobId);

  useEffect(() => {
    let cancelled = false;
    checkBackendHealth().then((online) => {
      if (!cancelled) setBackendOnline(online);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const isRunning = status != null && status.stage !== "done" && status.stage !== "failed";

  async function handleSubmit(payload: GenerateRequest) {
    setSubmitError(null);
    try {
      const response = await createJob(payload);
      setJobId(response.job_id);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Error inesperado al iniciar el trabajo.");
    }
  }

  function handleReset() {
    setJobId(null);
    setSubmitError(null);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>YouTube → Anki</h1>
        <p className="app-subtitle">
          Convierte cualquier video de YouTube en un mazo de Anki con tarjetas de video y
          subtítulos, 100% local.
        </p>
      </header>

      {backendOnline === false && (
        <ErrorBanner message="No se pudo conectar con el backend local. Verifica que el servidor esté corriendo." />
      )}

      <main className="app-main">
        {!jobId || status?.stage === "failed" ? (
          <UrlForm onSubmit={handleSubmit} disabled={isRunning} />
        ) : null}

        {submitError && <ErrorBanner message={submitError} onDismiss={() => setSubmitError(null)} />}
        {pollError && <ErrorBanner message={`Problema de conexión: ${pollError}`} />}

        {status && (
          <section className="status-section">
            <StageIndicator currentStage={status.stage} />
            <ProgressBar
              stage={status.stage}
              progressPercent={status.progress_percent}
              message={status.message}
              etaSeconds={status.estimated_seconds_remaining}
            />

            {status.stage === "failed" && status.error && (
              <ErrorBanner message={status.error} />
            )}

            {status.stage === "done" && (
              <div className="done-panel">
                <p>✅ Tu mazo de Anki está listo.</p>
                <a
                  className="download-button"
                  href={getDownloadUrl(status.job_id)}
                  download
                >
                  Descargar .apkg
                </a>
                <button type="button" className="secondary-button" onClick={handleReset}>
                  Generar otro mazo
                </button>
              </div>
            )}

            {status.stage === "failed" && (
              <button type="button" className="secondary-button" onClick={handleReset}>
                Intentar de nuevo
              </button>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
