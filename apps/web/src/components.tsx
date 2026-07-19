import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@shadowgrid/api-client";

export const Panel = ({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) => (
  <section className={`panel ${className}`}>
    {title && <h2>{title}</h2>}
    {children}
  </section>
);

export const Metric = ({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  tone?: "default" | "warning" | "good";
}) => (
  <div className={`metric metric--${tone}`}>
    <span className="metric__label">{label}</span>
    <strong>{value}</strong>
  </div>
);

export const Progress = ({
  label,
  value,
}: {
  label: string;
  value: number;
}) => (
  <div className="progress">
    <div className="progress__text">
      <span>{label}</span>
      <span>{Math.round(value)}</span>
    </div>
    <div className="progress__track" aria-hidden="true">
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  </div>
);

export const StateView = ({
  loading,
  error,
  empty,
  children,
  onRetry,
}: {
  loading?: boolean;
  error?: unknown;
  empty?: boolean;
  children: ReactNode;
  onRetry?: () => void;
}) => {
  const { t } = useTranslation();
  if (loading)
    return (
      <div className="state" role="status">
        <span className="spinner" aria-hidden="true" />
        {t("loading")}
      </div>
    );
  if (error) {
    const apiError = error instanceof ApiError ? error : null;
    const offline = !navigator.onLine || error instanceof TypeError;
    return (
      <div className="state state--error" role="alert">
        <h2>{t(offline ? "offlineTitle" : "errorTitle")}</h2>
        <p>
          {offline ? t("offlineBody") : (apiError?.message ?? t("errorTitle"))}
        </p>
        {apiError?.requestId && (
          <small>{t("requestId", { id: apiError.requestId })}</small>
        )}
        {onRetry && (
          <button className="button" onClick={onRetry}>
            {t("retry")}
          </button>
        )}
      </div>
    );
  }
  if (empty)
    return (
      <div className="state">
        <p>{t("empty")}</p>
      </div>
    );
  return <>{children}</>;
};

export const Field = ({
  label,
  children,
  hint,
  error,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  error?: string;
}) => {
  const id = `field-${label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
  return (
    <label className="field" htmlFor={id}>
      <span>{label}</span>
      {typeof children === "object" && children && "props" in children ? (
        <span className="field__control">{children}</span>
      ) : (
        children
      )}
      {hint && <small>{hint}</small>}
      {error && (
        <small className="field__error" role="alert">
          {error}
        </small>
      )}
    </label>
  );
};

export const Status = ({
  value,
  uncertain = false,
}: {
  value: string;
  uncertain?: boolean;
}) => (
  <span className={`status ${uncertain ? "status--uncertain" : ""}`}>
    <span aria-hidden="true">{uncertain ? "?" : "●"}</span>
    {value.replaceAll("_", " ")}
  </span>
);
