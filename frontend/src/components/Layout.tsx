import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n/I18nContext";
import { LANGS } from "../i18n/translate";

export function LangSwitch() {
  const { lang, setLang } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label="Language">
      {LANGS.map((code) => (
        <button key={code} type="button" className={code === lang ? "active" : ""} onClick={() => setLang(code)}>{code.toUpperCase()}</button>
      ))}
    </div>
  );
}

// Later features add their nav entries here.
const NAV = [["/", "nav.home"], ["/clients", "nav.clients"]];

export function Layout() {
  const { t } = useI18n();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="brand-drop" /><strong>{t("brand.name")}</strong></div>
        <nav className="nav" aria-label="Main">
          {NAV.map(([to, key]) => <NavLink key={to} to={to} end={to === "/"}>{t(key)}</NavLink>)}
        </nav>
        <div className="topbar-end">
          <LangSwitch />
          <span>{user?.full_name}</span>
          <button type="button" className="btn ghost small" onClick={() => logout().then(() => navigate("/login"))}>{t("nav.logout")}</button>
        </div>
      </header>
      <main className="content"><Outlet /></main>
    </div>
  );
}
