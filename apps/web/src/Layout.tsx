import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { NotificationCount } from "@shadowgrid/shared-types";
import { useQuery } from "@tanstack/react-query";
import { client, logout, useAuth } from "./auth";
import { useMultiplayerRealtime } from "./realtime";

const nav = [
  ["/command", "navCommand"],
  ["/engagement", "navEngagement"],
  ["/legacy", "navLegacy"],
  ["/city", "navCity"],
  ["/germany", "navGermany"],
  ["/network", "navNetwork"],
  ["/companies", "navBusinesses"],
  ["/exchange", "navExchange"],
  ["/specialists", "navSpecialists"],
  ["/operations", "navOperations"],
  ["/intelligence", "navIntelligence"],
  ["/cartels", "navOrganization"],
  ["/pvp", "navPvp"],
  ["/territories", "navTerritories"],
  ["/wars", "navWars"],
  ["/alliances", "navAlliances"],
  ["/communications", "navCommunications"],
  ["/market", "navMarket"],
  ["/contracts", "navContracts"],
  ["/finance", "navFinance"],
  ["/bonds", "navBonds"],
  ["/real-estate", "navRealEstate"],
  ["/diplomacy", "navDiplomacy"],
  ["/investigation", "navInvestigation"],
  ["/research", "navResearch"],
  ["/news", "navNews"],
  ["/rankings", "navRankings"],
  ["/settings", "navSettings"],
] as const;

const glyphPaths = [
  "M4 12h16M12 4v16M7 7l10 10M17 7 7 17",
  "M5 17 9 9l4 4 6-8M5 20h14",
  "M5 6h14v12H5zM8 10h8M8 14h5",
  "M12 3l8 5v8l-8 5-8-5V8zM12 8v8",
  "M4 16l5-5 4 3 7-8M17 6h3v3",
  "M6 5h12v14H6zM9 8h6v3H9zM9 14h2M13 14h2",
] as const;

function NavGlyph({ index }: { index: number }) {
  return (
    <span className="nav-glyph" aria-hidden="true">
      <svg viewBox="0 0 24 24" focusable="false">
        <path d={glyphPaths[index % glyphPaths.length]} />
      </svg>
    </span>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuth((state) => state.user);
  const unread = useQuery({
    queryKey: ["notification-unread-count"],
    queryFn: () => client.get<NotificationCount>("/notifications/unread-count"),
  });
  useMultiplayerRealtime();
  useEffect(() => setOpen(false), [location.pathname]);
  return (
    <div className="app-shell">
      <div className="app-shell__ambient" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <a href="#main" className="skip-link">
        {t("skipToContent")}
      </a>
      <header className="topbar">
        <NavLink to="/command" className="brand">
          <img
            className="brand__logo"
            src="/assets/branding/shadowgrid-logo-horizontal-dark.svg"
            alt={t("appName")}
          />
          <span className="brand__pulse" aria-hidden="true" />
        </NavLink>
        <div className="topbar__actions">
          <span className="topbar__signal" aria-hidden="true" />
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
        <span className="sidebar__rail" aria-hidden="true" />
        <nav id="primary-navigation" aria-label={t("primaryNavigation")}>
          {nav.map(([to, key], index) => (
            <NavLink key={to} to={to}>
              <NavGlyph index={index} />
              <span>{t(key)}</span>
              {key === "navNews" && (unread.data?.unread_count ?? 0) > 0 && (
                <span
                  className="nav-badge"
                  aria-label={t("unreadCount", {
                    count: unread.data?.unread_count ?? 0,
                  })}
                >
                  {unread.data?.unread_count}
                </span>
              )}
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
