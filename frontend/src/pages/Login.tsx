import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { LangSwitch } from "../components/Layout";
import { Field } from "../components/ui";
import { useI18n } from "../i18n/I18nContext";

const DEMO_ACCOUNTS = ["admin@aquacontrol.example", "supervisor@aquacontrol.example", "tech@aquacontrol.example"];

export function LoginPage() {
  const { t } = useI18n();
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const target = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to={target} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login(email, password).then(() => navigate(target, { replace: true }), (err) => setError(errorMessage(err)));
  };

  return (
    <div className="login-page">
      <section className="card login-card">
        <LangSwitch />
        <h1>{t("brand.name")}</h1>
        <p className="lede">{t("login.tagline")}</p>
        <form onSubmit={submit} className="form">
          <Field label={t("login.email")}><input autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
          <Field label={t("login.password")}><input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
          {error && <div className="flash error" role="alert">{error}</div>}
          <button className="btn primary" type="submit">{t("login.submit")}</button>
        </form>
        <small>{t("login.demoHint")}</small>
        <ul className="demo-list">
          {DEMO_ACCOUNTS.map((a) => <li key={a}><button type="button" className="link" onClick={() => setEmail(a)}>{a}</button></li>)}
        </ul>
      </section>
    </div>
  );
}
