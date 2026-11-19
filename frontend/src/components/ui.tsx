import type { FormEvent, ReactNode } from "react";
import type { Direction, MeasurementStatus } from "../api/types";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
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
  const { t } = useI18n();
  if (state.error) return <div className="card flash error" role="alert">{errorMessage(state.error, t)}</div>;
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

/** Shared create-form shell: title, fields, error line, save/cancel. ``backLabel`` is an i18n key. */
export function FormPage(props: {
  title: string;
  backTo: string;
  backLabel?: string;
  error: string | null;
  /** While a request is in flight Save is disabled (no double submissions). */
  busy?: boolean;
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <>
      <Link className="back" to={props.backTo}>← {t(props.backLabel ?? "nav.clients")}</Link>
      <PageHeader title={props.title} />
      <form className="card form" onSubmit={props.onSubmit} aria-busy={props.busy || undefined}>
        {props.children}
        {props.error && <div className="flash error" role="alert">{props.error}</div>}
        <div className="actions">
          <button className="btn primary" type="submit" disabled={props.busy}>{t("common.save")}</button>
          <Link className="btn" to={props.backTo}>{t("common.cancel")}</Link>
        </div>
      </form>
    </>
  );
}

const BADGE_CLASS: Record<MeasurementStatus, string> = { OK: "ok", OUT_OF_RANGE: "out", NO_RULE: "none" };

/** Evaluation status as a colored pill; OUT_OF_RANGE adds an arrow and low/high. */
export function StatusBadge({ status, direction }: { status: MeasurementStatus; direction: Direction | null }) {
  const { t } = useI18n();
  const arrow = direction === "LOW" ? "↓ " : direction === "HIGH" ? "↑ " : "";
  return (
    <span className={`badge ${BADGE_CLASS[status]}`} data-status={status}>
      {arrow}
      {t(`status.${status}`)}
      {direction && ` (${t(`direction.${direction}`)})`}
    </span>
  );
}
