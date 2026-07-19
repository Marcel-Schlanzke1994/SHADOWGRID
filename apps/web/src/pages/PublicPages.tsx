import { useEffect, useState, type FormEvent } from "react";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { useTranslation } from "react-i18next";
import { client, login, useAuth } from "../auth";
import { Field, Panel, StateView } from "../components";

const PublicFrame = ({ children }: { children: React.ReactNode }) => {
  const { t } = useTranslation();
  return (
    <main className="public-shell">
      <div className="public-brand">
        <span className="brand__mark" aria-hidden="true">
          SG
        </span>
        <strong>{t("appName")}</strong>
      </div>
      {children}
    </main>
  );
};

export function LandingPage() {
  const { t } = useTranslation();
  return (
    <PublicFrame>
      <section className="hero">
        <p className="eyebrow">{t("seasonEyebrow")}</p>
        <h1>{t("landingTitle")}</h1>
        <p>{t("landingBody")}</p>
        <div className="hero__actions">
          <Link className="button" to="/login">
            {t("playNow")}
          </Link>
          <Link className="button button--ghost" to="/register">
            {t("register")}
          </Link>
        </div>
        <small>{t("fictionalNotice")}</small>
      </section>
      <div className="hero-grid" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
        <span />
        <span />
      </div>
    </PublicFrame>
  );
}

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const authenticated = useAuth((state) => state.status === "authenticated");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  if (authenticated) return <Navigate to="/command" replace />;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    const data = new FormData(event.currentTarget);
    try {
      await login(
        String(data.get("email")),
        String(data.get("password")),
        String(data.get("totp") ?? ""),
      );
      navigate(
        (location.state as { from?: string } | null)?.from ?? "/command",
      );
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  };
  return (
    <PublicFrame>
      <Panel className="auth-card">
        <h1>{t("authWelcome")}</h1>
        <StateView error={error} loading={busy}>
          <form onSubmit={submit}>
            <Field label={t("email")}>
              <input
                id="field-email-address"
                name="email"
                type="email"
                autoComplete="email"
                required
              />
            </Field>
            <Field label={t("password")}>
              <input
                id="field-password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </Field>
            <Field label={t("totp")} hint={t("optional")}>
              <input
                id="field-two-factor-code"
                name="totp"
                inputMode="numeric"
                pattern="[0-9]{6}"
                autoComplete="one-time-code"
              />
            </Field>
            <button className="button" type="submit">
              {t("signIn")}
            </button>
          </form>
        </StateView>
        <div className="auth-links">
          <Link to="/forgot-password">{t("forgotPassword")}</Link>
          <Link to="/register">{t("register")}</Link>
        </div>
        <small>{t("localDemo")}</small>
      </Panel>
    </PublicFrame>
  );
}

export function RegisterPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<{
    busy: boolean;
    error?: unknown;
    done: boolean;
  }>({ busy: false, done: false });
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setState({ busy: true, done: false });
    try {
      await client.post("/auth/register", {
        email: data.get("email"),
        display_name: data.get("displayName"),
        password: data.get("password"),
        locale: navigator.language,
        terms_accepted: data.get("terms") === "on",
      });
      setState({ busy: false, done: true });
    } catch (error) {
      setState({ busy: false, done: false, error });
    }
  };
  return (
    <PublicFrame>
      <Panel className="auth-card">
        <h1>{t("register")}</h1>
        <p>{t("authRegisterIntro")}</p>
        {state.done ? (
          <p className="notice notice--success" role="status">
            {t("authCheckEmail")}
          </p>
        ) : (
          <StateView loading={state.busy} error={state.error}>
            <form onSubmit={submit}>
              <Field label={t("displayName")}>
                <input
                  id="field-display-name"
                  name="displayName"
                  minLength={2}
                  maxLength={40}
                  required
                />
              </Field>
              <Field label={t("email")}>
                <input
                  id="field-email-address"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                />
              </Field>
              <Field label={t("password")}>
                <input
                  id="field-password"
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  minLength={12}
                  required
                />
              </Field>
              <label className="checkbox">
                <input name="terms" type="checkbox" required />
                {t("terms")}
              </label>
              <button className="button" type="submit">
                {t("register")}
              </button>
            </form>
          </StateView>
        )}
        <Link to="/login">{t("signIn")}</Link>
      </Panel>
    </PublicFrame>
  );
}

export function TokenPage({ kind }: { kind: "verify" | "reset" }) {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [state, setState] = useState<{
    loading: boolean;
    error?: unknown;
    done: boolean;
  }>({ loading: kind === "verify", done: false });
  const token = params.get("token") ?? "";
  useEffect(() => {
    if (kind === "verify" && token)
      void client
        .post("/auth/verify-email", { token })
        .then(() => setState({ loading: false, done: true }))
        .catch((error) => setState({ loading: false, done: false, error }));
  }, [kind, token]);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setState({ loading: true, done: false });
    try {
      const password = new FormData(event.currentTarget).get("password");
      await client.post("/auth/password/reset", { token, password });
      setState({ loading: false, done: true });
    } catch (error) {
      setState({ loading: false, done: false, error });
    }
  };
  return (
    <PublicFrame>
      <Panel className="auth-card">
        <h1>{t(kind === "verify" ? "verifyEmail" : "resetPassword")}</h1>
        <StateView loading={state.loading} error={state.error}>
          {state.done ? (
            <Link className="button" to="/login">
              {t("signIn")}
            </Link>
          ) : kind === "reset" ? (
            <form onSubmit={submit}>
              <Field label={t("password")}>
                <input
                  id="field-password"
                  name="password"
                  type="password"
                  minLength={12}
                  required
                />
              </Field>
              <button className="button">{t("resetPassword")}</button>
            </form>
          ) : null}
        </StateView>
      </Panel>
    </PublicFrame>
  );
}

export function ForgotPage() {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>();
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await client.post("/auth/password/forgot", {
        email: new FormData(event.currentTarget).get("email"),
      });
      setDone(true);
    } catch (reason) {
      setError(reason);
    }
  };
  return (
    <PublicFrame>
      <Panel className="auth-card">
        <h1>{t("forgotPassword")}</h1>
        <StateView error={error}>
          {done ? (
            <p role="status">{t("authCheckEmail")}</p>
          ) : (
            <form onSubmit={submit}>
              <Field label={t("email")}>
                <input
                  id="field-email-address"
                  name="email"
                  type="email"
                  required
                />
              </Field>
              <button className="button">{t("resetPassword")}</button>
            </form>
          )}
        </StateView>
      </Panel>
    </PublicFrame>
  );
}
