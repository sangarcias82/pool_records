import { useState, type KeyboardEvent } from "react";
import { errorMessage } from "../api/client";
import { normRules as ruleApi } from "../api/endpoints";
import type { Classification, NormRule } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Card, Loaded, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useI18n } from "../i18n/I18nContext";
import { formatDateTime, formatRange } from "../lib/format";
import { paramLabel } from "../lib/labels";
import { draftFromRule, ruleChanges, type RuleDraft } from "../lib/rules";

const CLASSIFICATIONS: Classification[] = ["NORMATIVE", "COMPLEMENTARY"];

/** Everyone reads the organization's rules; ``can.manage_norm_rules`` (ORG_ADMIN) edits them inline. */
export function NormRulesPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const state = useAsync(ruleApi.list, []);
  const canEdit = Boolean(user?.can.manage_norm_rules);

  return (
    <>
      <PageHeader title={t("rules.heading")} lede={t("rules.lede", { org: user?.organization.name ?? "" })} />
      {!canEdit && <div className="flash info" role="note">{t("rules.readOnly")}</div>}
      <Loaded state={state}>{(rules) => <RulesTable initial={rules} canEdit={canEdit} />}</Loaded>
    </>
  );
}

function RulesTable({ initial, canEdit }: { initial: NormRule[]; canEdit: boolean }) {
  const { t } = useI18n();
  const [rules, setRules] = useState(initial);
  const [editing, setEditing] = useState<number | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const saved = (updated: NormRule | null, label: string) => {
    if (updated) setRules((list) => list.map((r) => (r.id === updated.id ? updated : r)));
    setFlash(updated ? t("rules.saved", { parameter: label }) : t("rules.noChanges"));
    setEditing(null);
  };

  return (
    <Card>
      {flash && <div className="flash" role="status">{flash}</div>}
      <div className="table-wrap">
        <table className="table rules">
          <thead>
            <tr>
              <th>{t("field.parameter")}</th>
              <th>{t("field.min")} – {t("field.max")}</th>
              <th>{t("field.classification")}</th>
              <th>{t("field.status")}</th>
              <th>{t("field.lastChange")}</th>
              {canEdit && <th aria-label={t("rules.edit")} />}
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) =>
              editing === rule.id ? (
                <EditRow key={rule.id} rule={rule} onDone={saved} onCancel={() => setEditing(null)} />
              ) : (
                <ViewRow key={rule.id} rule={rule} canEdit={canEdit} onEdit={() => { setFlash(null); setEditing(rule.id); }} />
              ),
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ParameterCell({ rule }: { rule: NormRule }) {
  const { t } = useI18n();
  return (
    <td>
      <strong>{paramLabel(t, rule.parameter_code, rule.parameter_name)}</strong>
      {rule.unit && <small> ({rule.unit})</small>}
      {rule.source_notes && <><br /><small className="note">{rule.source_notes}</small></>}
    </td>
  );
}

function ViewRow({ rule, canEdit, onEdit }: { rule: NormRule; canEdit: boolean; onEdit: () => void }) {
  const { t, lang } = useI18n();
  const zone = useAuth().user?.organization.timezone;
  const label = paramLabel(t, rule.parameter_code, rule.parameter_name);
  return (
    <tr data-rule={rule.parameter_code} data-active={rule.active}>
      <ParameterCell rule={rule} />
      <td className="nowrap">{formatRange(rule.min_value, rule.max_value, rule.decimals, lang)}</td>
      <td>{t(`class.${rule.classification}`)}</td>
      <td><span className={`badge ${rule.active ? "ok" : "none"}`}>{rule.active ? t("rules.active") : t("rules.inactive")}</span></td>
      <td>
        {rule.updated_at ? (
          <small>{t("rules.editedBy", { name: rule.updated_by_name ?? "", date: formatDateTime(rule.updated_at, lang, zone) })}</small>
        ) : (
          <span className="tag">{t("rules.planningDefault")}</span>
        )}
      </td>
      {canEdit && (
        <td>
          <button type="button" className="btn small" onClick={onEdit} aria-label={t("rules.editTitle", { parameter: label })}>
            {t("rules.edit")}
          </button>
        </td>
      )}
    </tr>
  );
}

function EditRow({ rule, onDone, onCancel }: { rule: NormRule; onDone: (r: NormRule | null, label: string) => void; onCancel: () => void }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<RuleDraft>(() => draftFromRule(rule));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const label = paramLabel(t, rule.parameter_code, rule.parameter_name);
  const change = (patch: Partial<RuleDraft>) => {
    setDraft({ ...draft, ...patch });
    setError(null); // the message described the previous attempt
  };

  const save = () => {
    const patch = ruleChanges(rule, draft);
    if (Object.keys(patch).length === 0) return onDone(null, label);
    setBusy(true);
    ruleApi.update(rule.id, patch).then(
      (updated) => onDone(updated, label),
      (err) => {
        setError(errorMessage(err, t));
        setBusy(false);
      },
    );
  };
  const keys = (e: KeyboardEvent) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") onCancel();
  };

  return (
    <>
      <tr className="editing" data-rule={rule.parameter_code}>
        <ParameterCell rule={rule} />
        <td>
          <div className="bounds">
            <input aria-label={t("field.min")} name="min_value" value={draft.min_value} inputMode="decimal" onChange={(e) => change({ min_value: e.target.value })} onKeyDown={keys} autoFocus />
            <span>–</span>
            <input aria-label={t("field.max")} name="max_value" value={draft.max_value} inputMode="decimal" onChange={(e) => change({ max_value: e.target.value })} onKeyDown={keys} />
          </div>
          <small>{t("rules.boundHint")}</small>
        </td>
        <td>
          <select aria-label={t("field.classification")} name="classification" value={draft.classification} onChange={(e) => change({ classification: e.target.value as Classification })}>
            {CLASSIFICATIONS.map((c) => <option key={c} value={c}>{t(`class.${c}`)}</option>)}
          </select>
        </td>
        <td>
          <label className="check">
            <input type="checkbox" name="active" checked={draft.active} onChange={(e) => change({ active: e.target.checked })} /> {t("field.active")}
          </label>
        </td>
        <td colSpan={2}>
          <div className="actions">
            <button type="button" className="btn primary small" onClick={save} disabled={busy}>{t("common.save")}</button>
            <button type="button" className="btn small" onClick={onCancel}>{t("common.cancel")}</button>
          </div>
        </td>
      </tr>
      {error && (
        <tr className="editing">
          <td colSpan={6}><div className="flash error" role="alert">{error}</div></td>
        </tr>
      )}
    </>
  );
}
