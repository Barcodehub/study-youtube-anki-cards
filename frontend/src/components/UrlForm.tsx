import { FormEvent, useState } from "react";
import type { GenerateRequest, LLMProviderName } from "../types";

interface UrlFormProps {
  onSubmit: (payload: GenerateRequest) => void;
  disabled: boolean;
}

const LANGUAGE_OPTIONS = [
  { code: "en", label: "Inglés" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Francés" },
  { code: "de", label: "Alemán" },
  { code: "pt", label: "Portugués" },
  { code: "ja", label: "Japonés" },
];

const PROVIDER_OPTIONS: { value: LLMProviderName; label: string }[] = [
  { value: "deepseek", label: "DeepSeek" },
  { value: "claude", label: "Claude (Anthropic)" },
  { value: "openai", label: "OpenAI" },
];

export function UrlForm({ onSubmit, disabled }: UrlFormProps) {
  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState("en");
  const [llmProvider, setLlmProvider] = useState<LLMProviderName>("deepseek");
  const [includeTranslation, setIncludeTranslation] = useState(false);
  const [translationLanguage, setTranslationLanguage] = useState("es");
  const [includePronunciationTips, setIncludePronunciationTips] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setValidationError(null);

    if (!isValidYouTubeUrl(url)) {
      setValidationError("Ingresa una URL de YouTube válida.");
      return;
    }

    onSubmit({
      url: url.trim(),
      language,
      llm_provider: llmProvider,
      include_translation: includeTranslation,
      translation_language: includeTranslation ? translationLanguage : null,
      include_pronunciation_tips: includePronunciationTips,
    });
  }

  return (
    <form className="url-form" onSubmit={handleSubmit}>
      <label className="field">
        <span>URL de YouTube</span>
        <input
          type="text"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={disabled}
          required
        />
      </label>

      <div className="field-row">
        <label className="field">
          <span>Idioma del video</span>
          <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={disabled}>
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.code} value={opt.code}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Proveedor de IA</span>
          <select
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value as LLMProviderName)}
            disabled={disabled}
          >
            {PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="field-row checkboxes">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={includePronunciationTips}
            onChange={(e) => setIncludePronunciationTips(e.target.checked)}
            disabled={disabled}
          />
          <span>Incluir tips de pronunciación nativa</span>
        </label>

        <label className="checkbox">
          <input
            type="checkbox"
            checked={includeTranslation}
            onChange={(e) => setIncludeTranslation(e.target.checked)}
            disabled={disabled}
          />
          <span>Incluir traducción</span>
        </label>

        {includeTranslation && (
          <select
            value={translationLanguage}
            onChange={(e) => setTranslationLanguage(e.target.value)}
            disabled={disabled}
          >
            <option value="es">Español</option>
            <option value="fr">Francés</option>
            <option value="de">Alemán</option>
            <option value="pt">Portugués</option>
          </select>
        )}
      </div>

      {validationError && <p className="field-error">{validationError}</p>}

      <button type="submit" className="generate-button" disabled={disabled}>
        {disabled ? "Generando..." : "Generar mazo de Anki"}
      </button>
    </form>
  );
}

function isValidYouTubeUrl(value: string): boolean {
  try {
    const parsed = new URL(value.trim());
    return /(^|\.)youtube\.com$/.test(parsed.hostname) || parsed.hostname === "youtu.be";
  } catch {
    return false;
  }
}
