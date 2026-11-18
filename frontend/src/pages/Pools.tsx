import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { pools as poolApi } from "../api/endpoints";
import type { Pool, PoolInput } from "../api/types";
import { Field, FormPage } from "../components/ui";
import { useI18n } from "../i18n/I18nContext";

export function PoolsTable({ rows }: { rows: Pool[] }) {
  const { t } = useI18n();
  if (rows.length === 0) return <p className="empty">{t("common.none")}</p>;
  return (
    <table className="table">
      <thead>
        <tr><th>{t("field.name")}</th><th>{t("field.volume")}</th><th>{t("field.environment")}</th></tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <tr key={p.id}>
            <td>{p.name}</td>
            <td>{p.volume_liters.toLocaleString()}</td>
            <td>{t(`env.${p.environment}`)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** New pool under the client in the URL (/clients/:clientId/pools/new). */
export function PoolFormPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const clientId = Number(useParams().clientId);
  const [form, setForm] = useState<PoolInput>({ environment: "OUTDOOR" });
  const [error, setError] = useState<string | null>(null);
  const bind = (key: keyof PoolInput) => ({
    value: form[key] ?? "",
    onChange: (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value }),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    poolApi.create(clientId, form).then(() => navigate(`/clients/${clientId}`), (err) => setError(errorMessage(err)));
  };

  return (
    <FormPage title={t("pools.new")} backTo={`/clients/${clientId}`} error={error} onSubmit={submit}>
      <Field label={t("field.name")}><input {...bind("name")} required /></Field>
      <Field label={t("field.volume")}><input inputMode="decimal" {...bind("volume_liters")} required /></Field>
      <Field label={t("field.environment")}>
        <select {...bind("environment")}>
          <option value="OUTDOOR">{t("env.OUTDOOR")}</option>
          <option value="INDOOR">{t("env.INDOOR")}</option>
        </select>
      </Field>
    </FormPage>
  );
}
