import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { measurements as measurementApi, normRules as ruleApi, parameters as parameterApi, pools as poolApi } from "../api/endpoints";
import type { Measurement, MeasurementStatus, NormRule, Pool, WaterParameter } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Card, Field, FormPage, Loaded, PageHeader, StatusBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useBusy } from "../hooks/useBusy";
import { useI18n } from "../i18n/I18nContext";
import { activeRuleFor, previewMeasurement, type Evaluation, type Preview } from "../lib/evaluation";
import { formatDateTime, formatDateTimeParts, formatNumber, formatRange, localInputToIso, toLocalInputValue } from "../lib/format";
import { paramLabel } from "../lib/labels";

const STATUSES: MeasurementStatus[] = ["OK", "OUT_OF_RANGE", "NO_RULE"];
const LIST_LIMIT = 200; // the API maximum; the page says so when a list is cut


const poolLabel = (p: Pool) => `${p.client_name} — ${p.name}`;

// --- List -------------------------------------------------------------------------------------------------

export function MeasurementsListPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const zone = user?.organization.timezone;
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const poolId = params.get("pool_id") ?? "";
  const status = (params.get("status") ?? "") as MeasurementStatus | "";
  const measuredFrom = params.get("measured_from") ?? ""; // set by the dashboard widgets
  const navState = location.state as { saved?: Measurement; previewed?: Evaluation | null } | null;
  const saved = navState?.saved;
  // The preview used the rules loaded with the form; if a rule changed meanwhile the stored result can differ.
  const differed =
    saved && navState?.previewed && (navState.previewed.status !== saved.status || navState.previewed.direction !== saved.direction);

  const pools = useAsync(poolApi.list, []);
  const rows = useAsync(
    () =>
      measurementApi.list({
        pool_id: poolId ? Number(poolId) : undefined,
        status: status || undefined,
        measured_from: measuredFrom || undefined,
        limit: LIST_LIMIT,
      }),
    [poolId, status, measuredFrom],
  );

  const setFilter = (key: "pool_id" | "status" | "measured_from", value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const add = user?.can.capture_measurements && (
    <Link className="btn primary" to={poolId ? `/measurements/new?pool_id=${poolId}` : "/measurements/new"}>{t("measurements.new")}</Link>
  );

  return (
    <>
      <PageHeader title={t("measurements.heading")} lede={t("measurements.lede")} actions={add} />
      {saved && (
        <div className="flash" role="status">
          {t("measurements.saved", {
            folio: saved.folio,
            status: t(`status.${saved.status}`) + (saved.direction ? ` (${t(`direction.${saved.direction}`)})` : ""),
          })}
          {differed && <><br /><strong>{t("measurements.previewDiffered")}</strong></>}
        </div>
      )}
      <Card>
        <div className="filters">
          <Field label={t("field.pool")}>
            <select value={poolId} onChange={(e) => setFilter("pool_id", e.target.value)} aria-label={t("field.pool")}>
              <option value="">{t("common.all")}</option>
              {(pools.data ?? []).map((p) => <option key={p.id} value={p.id}>{poolLabel(p)}</option>)}
            </select>
          </Field>
          <Field label={t("field.status")}>
            <select value={status} onChange={(e) => setFilter("status", e.target.value)} aria-label={t("field.status")}>
              <option value="">{t("common.all")}</option>
              {STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
            </select>
          </Field>
        </div>
        {measuredFrom && (
          <p className="chip">
            {t("measurements.since", { from: formatDateTime(measuredFrom, lang, zone) })}{" "}
            <button type="button" className="link" onClick={() => setFilter("measured_from", "")} aria-label={t("measurements.clearSince")}>
              ✕
            </button>
          </p>
        )}
        <Loaded state={rows}>
          {(list) =>
            list.length === 0 ? (
              <p className="empty">{t("measurements.empty")}</p>
            ) : (
              <>
                <p className="count">
                  <small>{t("measurements.count", { count: list.length })}</small>
                  {list.length >= LIST_LIMIT && <><br /><small className="truncated">{t("measurements.truncated", { count: LIST_LIMIT })}</small></>}
                </p>
                <div className="table-wrap">
                  <table className="table measurements">
                    <thead>
                      <tr>
                        <th>{t("field.folio")}</th>
                        <th>{t("field.measuredAt")}<br /><small>{t("field.recordedBy")}</small></th>
                        <th>{t("field.pool")}</th>
                        <th>{t("field.parameter")}</th>
                        <th className="num">{t("field.value")}</th>
                        <th>{t("field.rule")}</th>
                        <th>{t("field.status")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.map((m) => {
                        const when = formatDateTimeParts(m.measured_at, lang, zone);
                        return (
                        <tr key={m.id} data-status={m.status}>
                          <td className="mono">{m.folio}</td>
                          <td className="nowrap">{when.date}<br />{when.time}<br /><small>{m.recorded_by_name}</small></td>
                          <td>{m.pool_name}<br /><small>{m.client_name}</small></td>
                          <td>
                            {paramLabel(t, m.parameter_code, m.parameter_name)}
                            {m.notes && <><br /><small className="note">{m.notes}</small></>}
                          </td>
                          <td className="num">{formatNumber(m.value, m.decimals, lang)}{m.unit && <small> {m.unit}</small>}</td>
                          <td>
                            {m.rule_id === null ? "—" : formatRange(m.rule_min, m.rule_max, m.decimals, lang)}
                            {m.rule_classification && <><br /><small>{t(`class.${m.rule_classification}`)}</small></>}
                          </td>
                          <td><StatusBadge status={m.status} direction={m.direction} /></td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )
          }
        </Loaded>
      </Card>
    </>
  );
}

// --- New measurement ----------------------------------------------------------------------------------------

export function MeasurementFormPage() {
  const state = useAsync(() => Promise.all([poolApi.list(), parameterApi.list(), ruleApi.list()]), []);
  return <Loaded state={state}>{([pools, parameters, rules]) => <MeasurementForm pools={pools} parameters={parameters} rules={rules} />}</Loaded>;
}

interface FormState {
  pool_id: string;
  parameter_id: string;
  value: string;
  measured_at: string;
  notes: string;
}

function MeasurementForm({ pools, parameters, rules }: { pools: Pool[]; parameters: WaterParameter[]; rules: NormRule[] }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const [form, setForm] = useState<FormState>({
    pool_id: search.get("pool_id") ?? "",
    parameter_id: "",
    value: "",
    measured_at: toLocalInputValue(new Date()),
    notes: "",
  });
  const [error, setError] = useState<string | null>(null);
  const { busy, run } = useBusy();
  // Editing clears the last server error: it described the previous submission (and was in the language of then).
  const set = (key: keyof FormState) => (e: { target: { value: string } }) => {
    setForm({ ...form, [key]: e.target.value });
    setError(null);
  };

  const parameter = parameters.find((p) => String(p.id) === form.parameter_id) ?? null;
  const preview = previewMeasurement(form.value, parameter, rules);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const previewed = preview.kind === "evaluated" ? preview.evaluation : null;
    run(() => measurementApi
      .create({
        pool_id: Number(form.pool_id),
        parameter_id: Number(form.parameter_id),
        value: form.value,
        measured_at: localInputToIso(form.measured_at),
        notes: form.notes || undefined,
      })
      .then(
        (saved) => navigate("/measurements", { state: { saved, previewed } }),
        (err) => setError(errorMessage(err, t)),
      ));
  };

  return (
    <FormPage title={t("measurements.new")} backTo="/measurements" backLabel="nav.measurements" error={error} busy={busy} onSubmit={submit}>
      <Field label={t("field.pool")}>
        <select value={form.pool_id} onChange={set("pool_id")} required name="pool_id">
          <option value="">{t("measurements.choose")}</option>
          {pools.map((p) => <option key={p.id} value={p.id}>{poolLabel(p)}</option>)}
        </select>
      </Field>
      <Field label={t("field.parameter")}>
        <select value={form.parameter_id} onChange={set("parameter_id")} required name="parameter_id">
          <option value="">{t("measurements.choose")}</option>
          {parameters.map((p) => (
            <option key={p.id} value={p.id}>{paramLabel(t, p.code, p.name)}{p.unit ? ` (${p.unit})` : ""}</option>
          ))}
        </select>
      </Field>
      <Field label={t("field.value") + (parameter?.unit ? ` (${parameter.unit})` : "")}>
        <input value={form.value} onChange={set("value")} inputMode="decimal" autoComplete="off" required name="value" placeholder="7,4" />
        <small>{t("measurements.valueHint")}</small>
      </Field>
      <PreviewPanel preview={preview} parameter={parameter} rules={rules} />
      <Field label={t("field.measuredAt")}>
        <input type="datetime-local" value={form.measured_at} onChange={set("measured_at")} max={toLocalInputValue(new Date())} name="measured_at" />
        <small>{t("measurements.nowHint")}</small>
      </Field>
      <Field label={t("field.notes")}>
        <textarea value={form.notes} onChange={set("notes")} rows={2} maxLength={500} name="notes" />
      </Field>
    </FormPage>
  );
}

function PreviewPanel({ preview, parameter, rules }: { preview: Preview; parameter: WaterParameter | null; rules: NormRule[] }) {
  const { t, lang } = useI18n();
  const rule = parameter ? activeRuleFor(rules, parameter.id) : null;
  const label = parameter ? paramLabel(t, parameter.code, parameter.name) : "";
  const range = rule && parameter ? formatRange(rule.min_value, rule.max_value, parameter.decimals, lang, parameter.unit) : "";
  const fmt = (value: number) => formatNumber(value, parameter?.decimals ?? 0, lang);

  let body;
  if (preview.kind === "incomplete") {
    body = <p className="empty">{t("preview.incomplete")}</p>;
  } else if (preview.kind === "invalid") {
    body = <p className="preview-msg bad">{t("preview.invalid")}</p>;
  } else if (preview.kind === "impossible") {
    const physical = formatRange(parameter!.physical_min, parameter!.physical_max, parameter!.decimals, lang, parameter!.unit);
    body = <p className="preview-msg bad">{t("preview.impossible", { value: fmt(preview.value), parameter: label, range: physical })}</p>;
  } else {
    const { status, direction } = preview.evaluation;
    const message =
      status === "NO_RULE" ? t("preview.noRule", { parameter: label })
      : direction === "LOW" ? t("preview.low", { range })
      : direction === "HIGH" ? t("preview.high", { range })
      : t("preview.ok", { range });
    body = (
      <p className="preview-msg">
        <StatusBadge status={status} direction={direction} /> {message}
      </p>
    );
  }

  return (
    <section className="preview" aria-live="polite" data-preview-kind={preview.kind}>
      <strong>{t("preview.title")}</strong>
      {parameter && (
        <p className="preview-rule">
          {label}: {rule ? <>{range} <small>({t(`class.${rule.classification}`)})</small></> : t("status.NO_RULE")}
        </p>
      )}
      {body}
      <small>{t("preview.note")}</small>
    </section>
  );
}
