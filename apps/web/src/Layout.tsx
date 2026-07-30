import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { NotificationCount } from "@shadowgrid/shared-types";
import { useQuery } from "@tanstack/react-query";
import { client, logout, useAuth } from "./auth";
import { useMultiplayerRealtime } from "./realtime";

const nav = [
  ["/command", "navCommand"],
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
