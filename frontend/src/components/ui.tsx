import type { FormEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nContext";
import type { AsyncState } from "../hooks/useAsync";

export function PageHeader({ title, lede, actions }: { title: string; lede?: string; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Spinner() {
  const { t } = useI18n();
  return <div className="spinner">{t("common.loading")}</div>;
}

/** Renders loading / error / content for a ``useAsync`` result. */
export function Loaded<T>({ state, children }: { state: AsyncState<T>; children: (data: T) => ReactNode }) {
  if (state.error) return <div className="card flash error">{state.error}</div>;
  return state.data ? <>{children(state.data)}</> : <Spinner />;
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {title && <div className="card-head"><h2>{title}</h2>{actions}</div>}
      {children}
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

/** Shared create-form shell: title, fields, error line, save/cancel. Later features reuse it. */
export function FormPage(props: { title: string; backTo: string; error: string | null; onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <>
      <Link className="back" to={props.backTo}>← {t("nav.clients")}</Link>
      <PageHeader title={props.title} />
      <form className="card form" onSubmit={props.onSubmit}>
        {props.children}
        {props.error && <div className="flash error" role="alert">{props.error}</div>}
        <div className="actions">
          <button className="btn primary" type="submit">{t("common.save")}</button>
          <Link className="btn" to={props.backTo}>{t("common.cancel")}</Link>
        </div>
      </form>
    </>
  );
}
