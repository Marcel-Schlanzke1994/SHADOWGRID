import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { logout, useAuth } from "./auth";

const nav = [
  ["/command", "navCommand"],
  ["/city", "navCity"],
  ["/network", "navNetwork"],
  ["/businesses", "navBusinesses"],
  ["/specialists", "navSpecialists"],
  ["/operations", "navOperations"],
  ["/organizations", "navOrganization"],
  ["/diplomacy", "navDiplomacy"],
  ["/investigation", "navInvestigation"],
  ["/research", "navResearch"],
  ["/news", "navNews"],
  ["/rankings", "navRankings"],
  ["/settings", "navSettings"],
] as const;

export function Layout() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuth((state) => state.user);
  useEffect(() => setOpen(false), [location.pathname]);
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        {t("skipToContent")}
      </a>
      <header className="topbar">
        <NavLink to="/command" className="brand">
          <span className="brand__mark" aria-hidden="true">
            SG
          </span>
          <span>{t("appName")}</span>
        </NavLink>
        <div className="topbar__actions">
          <span className="topbar__user">{user?.display_name}</span>
          <button
            className="icon-button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls="primary-navigation"
          >
            <span aria-hidden="true">☰</span>
            <span className="sr-only">
              {t(open ? "closeMenu" : "openMenu")}
            </span>
          </button>
        </div>
      </header>
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <nav id="primary-navigation" aria-label={t("primaryNavigation")}>
          {nav.map(([to, key]) => (
            <NavLink key={to} to={to}>
              {t(key)}
            </NavLink>
          ))}
          {user?.is_admin && <NavLink to="/admin">{t("navAdmin")}</NavLink>}
          {(user?.is_admin || user?.is_moderator) && (
            <NavLink to="/moderation">{t("navModeration")}</NavLink>
          )}
        </nav>
        <button
          className="button button--ghost"
          onClick={() => void logout().then(() => navigate("/login"))}
        >
          {t("signOut")}
        </button>
      </aside>
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
