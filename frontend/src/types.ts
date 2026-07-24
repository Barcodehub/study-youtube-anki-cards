// Mirrors backend/app/api/schemas.py — keep these in sync manually, since
// the backend is the single source of truth for the contract.

export type LLMProviderName = "deepseek" | "claude" | "openai";

export type SubtitleMode = "auto" | "whisper_only" | "youtube_only";

export type JobStage =
  | "queued"
  | "downloading"
  | "subtitles"
  | "transcribing"
  | "segmenting"
  | "cutting"
  | "building_deck"
  | "cleaning_up"
  | "done"
  | "failed";

export interface GenerateRequest {
  url: string;
  language: string;
  llm_provider?: LLMProviderName | null;
  subtitle_mode: SubtitleMode;
  short_phrases: boolean;
  include_translation: boolean;
  translation_language?: string | null;
  include_pronunciation_tips: boolean;
}

export interface GenerateResponse {
  job_id: string;
}

export interface JobStatusResponse {
  job_id: string;
  stage: JobStage;
  progress_percent: number;
  message: string;
  error?: string | null;
  estimated_seconds_remaining?: number | null;
  output_file?: string | null;
}

export const STAGE_LABELS: Record<JobStage, string> = {
  queued: "En cola",
  downloading: "Descargando video",
  subtitles: "Procesando subtítulos",
  transcribing: "Transcribiendo con Whisper",
  segmenting: "Analizando contenido con IA",
  cutting: "Cortando segmentos de video",
  building_deck: "Generando mazo de Anki",
  cleaning_up: "Limpiando archivos temporales",
  done: "Completado",
  failed: "Error",
};

export const SUBTITLE_MODE_LABELS: Record<SubtitleMode, string> = {
  auto: "Automático (YouTube si existe, si no Whisper)",
  whisper_only: "Forzar Whisper (más fiel, sin filtro de groserías)",
  youtube_only: "Solo subtítulos de YouTube",
};