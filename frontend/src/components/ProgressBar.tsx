import type { JobStage } from "../types";
import { STAGE_LABELS } from "../types";

interface ProgressBarProps {
  stage: JobStage;
  progressPercent: number;
  message: string;
  etaSeconds?: number | null;
}

export function ProgressBar({ stage, progressPercent, message, etaSeconds }: ProgressBarProps) {
  const isFailed = stage === "failed";

  return (
    <div className="progress-panel">
      <div className="progress-header">
        <span className="stage-label">{STAGE_LABELS[stage]}</span>
        <span className="progress-percent">{progressPercent}%</span>
      </div>

      <div className="progress-track">
        <div
          className={`progress-fill ${isFailed ? "progress-fill--error" : ""}`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <p className="progress-message">{message}</p>

      {etaSeconds != null && etaSeconds > 0 && stage !== "done" && !isFailed && (
        <p className="progress-eta">Tiempo estimado restante: {formatEta(etaSeconds)}</p>
      )}
    </div>
  );
}

function formatEta(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainderSeconds = seconds % 60;
  return `${minutes}m ${remainderSeconds}s`;
}
