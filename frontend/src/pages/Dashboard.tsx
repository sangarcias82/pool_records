import { core } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Loaded, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useI18n } from "../i18n/I18nContext";

export function DashboardPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const state = useAsync(core.dashboard, []);

  return (
    <>
      <PageHeader title={t("home.heading")} lede={t("home.welcome", { name: user?.full_name ?? "" })} />
      <Loaded state={state}>
        {({ counts }) => (
          <div className="stats">
            {(["clients", "pools", "users"] as const).map((key) => (
              <div className="stat" key={key}>
                <strong>{counts[key]}</strong>
                <span>{t(`home.${key}`)}</span>
              </div>
            ))}
          </div>
        )}
      </Loaded>
    </>
  );
}
