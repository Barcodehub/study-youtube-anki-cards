interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert">
      <span className="error-icon">⚠</span>
      <span className="error-text">{message}</span>
      {onDismiss && (
        <button type="button" className="error-dismiss" onClick={onDismiss} aria-label="Cerrar">
          ✕
        </button>
      )}
    </div>
  );
}
