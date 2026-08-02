import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import { GlobalStateBackdrop } from "./GlobalBackdrop";

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
    <span className="panel__edge panel__edge--top" aria-hidden="true" />
    <span className="panel__edge panel__edge--bottom" aria-hidden="true" />
    {title && (
      <header className="panel__heading">
        <span className="panel__signal" aria-hidden="true" />
        <h2>{title}</h2>
      </header>
    )}
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
    <span className="metric__scan" aria-hidden="true" />
    <span className="metric__label">{label}</span>
    <strong>{value}</strong>
    <span className="metric__signal" aria-hidden="true" />
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
        <span>{t("loading")}</span>
        <span className="state__scan" aria-hidden="true" />
      </div>
    );
  if (error) {
    const apiError = error instanceof ApiError ? error : null;
    const offline = !navigator.onLine || error instanceof TypeError;
    const errorKey =
      apiError?.status === 401
        ? "errorUnauthorized"
        : apiError?.status === 403
          ? "errorForbidden"
          : apiError?.status === 404
            ? "errorNotFound"
            : apiError?.status === 409
              ? "errorConflict"
              : apiError?.status === 422
                ? "errorValidation"
                : apiError?.status === 429
                  ? "errorRateLimited"
                  : "errorServer";
    const errorState = (
      <div
        className={`state state--error ${offline ? "state--offline" : ""}`}
        role="alert"
      >
        <span className="state__emblem state__emblem--error" aria-hidden="true">
          <span />
        </span>
        <h2>{t(offline ? "offlineTitle" : "errorTitle")}</h2>
        <p>{offline ? t("offlineBody") : t(errorKey)}</p>
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
    if (!offline) return errorState;
    return (
      <div className="system-state system-state--offline">
        <GlobalStateBackdrop assetId="global-offline-v1" variant="offline" />
        {errorState}
      </div>
    );
  }
  if (empty)
    return (
      <div className="state state--empty" role="status">
        <span className="state__emblem" aria-hidden="true">
          <span />
        </span>
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
  const { t } = useTranslation();
  const uniqueId = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const id = `field-${label.toLowerCase().replace(/[^a-z0-9]/g, "-")}-${uniqueId}`;
  const controlId = isValidElement<{ id?: string }>(children)
    ? (children.props.id ?? id)
    : id;
  const control = isValidElement<{ id?: string }>(children)
    ? cloneElement(children, { id: controlId })
    : children;
  return (
    <label className="field" htmlFor={controlId}>
      <span>{label}</span>
      {isValidElement(control) ? (
        <span className="field__control">{control}</span>
      ) : (
        control
      )}
      {hint && <small>{hint}</small>}
      {error && (
        <small className="field__error" role="alert">
          {t("formFieldInvalid")}
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
    {translateGameValue(value)}
  </span>
);

export const ConfirmDialog = ({
  title,
  description,
  confirmLabel,
  cancelLabel,
  pending = false,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) => {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    }
    return () => {
      if (element?.open && typeof element.close === "function") element.close();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="confirm-dialog"
      aria-labelledby="confirm-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onCancel();
      }}
    >
      <h2 id="confirm-dialog-title">{title}</h2>
      <div>{description}</div>
      <div className="button-row">
        <button
          className="button button--ghost"
          type="button"
          disabled={pending}
          onClick={onCancel}
        >
          {cancelLabel}
        </button>
        <button
          className="button"
          type="button"
          disabled={pending}
          aria-busy={pending}
          onClick={onConfirm}
        >
          <span>{confirmLabel}</span>
        </button>
      </div>
    </dialog>
  );
};
