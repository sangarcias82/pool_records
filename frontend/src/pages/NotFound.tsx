import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nContext";

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <div className="card">
      <h1>404</h1>
      <p>{t("notfound.title")}</p>
      <Link className="btn primary" to="/">{t("nav.home")}</Link>
    </div>
  );
}
