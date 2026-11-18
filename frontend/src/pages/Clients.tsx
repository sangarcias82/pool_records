import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { clients as clientApi } from "../api/endpoints";
import type { ClientInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Card, Field, FormPage, Loaded, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useI18n } from "../i18n/I18nContext";
import { PoolsTable } from "./Pools";

export function ClientsListPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const state = useAsync(clientApi.list, []);
  const add = user?.can.manage_clients && <Link className="btn primary" to="/clients/new">{t("clients.new")}</Link>;

  return (
    <>
      <PageHeader title={t("clients.heading")} actions={add} />
      <Loaded state={state}>
        {(rows) => (
          <Card>
            <table className="table">
              <thead><tr><th>{t("field.name")}</th><th>{t("field.contact")}</th><th>{t("clients.pools")}</th></tr></thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td><Link to={`/clients/${c.id}`}>{c.name}</Link></td>
                    <td>{c.contact_name ?? "—"}</td>
                    <td>{c.pool_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </Loaded>
    </>
  );
}

export function ClientDetailPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const id = Number(useParams().id);
  const state = useAsync(() => clientApi.get(id), [id]);
  const add = user?.can.manage_clients && <Link className="btn primary small" to={`/clients/${id}/pools/new`}>{t("pools.new")}</Link>;

  return (
    <>
      <Link className="back" to="/clients">← {t("clients.heading")}</Link>
      <Loaded state={state}>
        {(c) => (
          <>
            <PageHeader title={c.name} lede={[c.contact_name, c.email, c.phone, c.address].filter(Boolean).join(" · ")} />
            <Card title={t("clients.pools")} actions={add}>
              <PoolsTable rows={c.pools ?? []} />
            </Card>
          </>
        )}
      </Loaded>
    </>
  );
}

const FIELDS = [
  ["name", "field.name"],
  ["contact_name", "field.contact"],
  ["email", "field.email"],
  ["phone", "field.phone"],
  ["address", "field.address"],
] as const;

export function ClientFormPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [form, setForm] = useState<ClientInput>({});
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    clientApi.create(form).then((created) => navigate(`/clients/${created.id}`), (err) => setError(errorMessage(err)));
  };

  return (
    <FormPage title={t("clients.new")} backTo="/clients" error={error} onSubmit={submit}>
      {FIELDS.map(([key, label]) => (
        <Field key={key} label={t(label)}>
          <input value={form[key] ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} required={key === "name"} />
        </Field>
      ))}
    </FormPage>
  );
}
