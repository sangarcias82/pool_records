import { Link } from "react-router-dom";
import { core } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Loaded, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { useI18n } from "../i18n/I18nContext";
import { formatDateTimeParts } from "../lib/format";

/** ``/measurements`` link for a widget; the same window start the server counted with. */
function listLink(from: string, status?: string): string {
  const query = new URLSearchParams({ measured_from: from, ...(status ? { status } : {}) });
  return `/measurements?${query.toString()}`;
}

export function DashboardPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const state = useAsync(core.dashboard, []);

  return (
    <>
      <PageHeader title={t("home.heading")} lede={t("home.welcome", { name: user?.full_name ?? "" })} />
      <Loaded state={state}>
        {({ counts, measurements, windows }) => {
          const day = (iso: string) => formatDateTimeParts(iso, lang, windows.timezone).date;
          const out = measurements.out_of_range_last_7_days;
          return (
            <>
              <div className="stats widgets">
                <Link className="stat widget" to={listLink(windows.today_from)} data-widget="today">
                  <strong>{measurements.today}</strong>
                  <span>{t("home.measurementsToday")}</span>
                  <small>{t("home.windowToday", { from: day(windows.today_from) })}</small>
                </Link>
                <Link className={`stat widget ${out > 0 ? "alert" : ""}`} to={listLink(windows.last_7_days_from, "OUT_OF_RANGE")} data-widget="out-of-range">
                  <strong>{out}</strong>
                  <span>{t("home.outOfRange7d")}</span>
                  <small>{t("home.window7d", { from: day(windows.last_7_days_from) })}</small>
                </Link>
              </div>
              <p className="window-note"><small>{t("home.windowNote", { zone: windows.timezone })}</small></p>
              <div className="stats">
                {(["clients", "pools", "users"] as const).map((key) => (
                  <div className="stat" key={key}>
                    <strong>{counts[key]}</strong>
                    <span>{t(`home.${key}`)}</span>
                  </div>
                ))}
              </div>
            </>
          );
        }}
      </Loaded>
    </>
  );
}
