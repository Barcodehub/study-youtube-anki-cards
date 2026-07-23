import type { JobStage } from "../types";

const PIPELINE_STAGES: { key: JobStage; label: string }[] = [
  { key: "downloading", label: "Descarga" },
  { key: "subtitles", label: "Subtítulos" },
  { key: "transcribing", label: "Transcripción" },
  { key: "segmenting", label: "Segmentación IA" },
  { key: "cutting", label: "Corte de video" },
  { key: "building_deck", label: "Mazo Anki" },
];

interface StageIndicatorProps {
  currentStage: JobStage;
}

export function StageIndicator({ currentStage }: StageIndicatorProps) {
  const currentIndex = PIPELINE_STAGES.findIndex((s) => s.key === currentStage);
  const isDone = currentStage === "done";
  const isFailed = currentStage === "failed";

  return (
    <ol className="stage-indicator">
      {PIPELINE_STAGES.map((stage, index) => {
        // "subtitles" and "transcribing" are alternative paths (mutually
        // exclusive branches of the same step), so treat reaching either as
        // completing that logical step for display purposes.
        const effectiveIndex =
          currentIndex === -1 && isDone ? PIPELINE_STAGES.length : currentIndex;

        let statusClass = "pending";
        if (isFailed && index === Math.max(effectiveIndex, 0)) {
          statusClass = "failed";
        } else if (effectiveIndex > index || isDone) {
          statusClass = "complete";
        } else if (effectiveIndex === index) {
          statusClass = "active";
        }

        return (
          <li key={stage.key} className={`stage-item stage-item--${statusClass}`}>
            <span className="stage-dot" />
            <span className="stage-text">{stage.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
