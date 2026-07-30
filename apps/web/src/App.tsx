import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { bootstrapAuth, useAuth } from "./auth";
import { Layout } from "./Layout";
import { StateView } from "./components";
import {
  ForgotPage,
  LandingPage,
  LoginPage,
  RegisterPage,
  TokenPage,
} from "./pages/PublicPages";
import {
  WorldPage,
  TutorialPage,
  DashboardPage,
  CityPage,
  BusinessesPage,
  FacilitiesPage,
  SpecialistsPage,
  OperationsPage,
  NetworkPage,
  InvestigationPage,
} from "./pages/CorePages";
import { GermanyPage } from "./pages/GermanyPage";
import { ExchangePage } from "./pages/ExchangePage";
import { CartelsPage } from "./pages/CartelsPage";
import { ContractsPage } from "./pages/ContractsPage";
import { FinancePage } from "./pages/FinancePage";
import { BondsPage } from "./pages/BondsPage";
import { RealEstatePage } from "./pages/RealEstatePage";
import { IntelligencePage } from "./pages/IntelligencePage";
import {
  DiplomacyPage,
  ResearchPage,
  NewsPage,
  RankingsPage,
  SettingsPage,
  AdminPage,
  ModerationPage,
} from "./pages/SocialPages";
import {
  AlliancesPage,
  CommunicationsPage,
  MarketPage,
  PvpPage,
  TerritoriesPage,
  WarsPage,
} from "./pages/MultiplayerPages";

function Protected({ children }: { children: React.ReactNode }) {
  const status = useAuth((state) => state.status);
  const location = useLocation();
  const { t } = useTranslation();
  if (status === "loading")
    return (
      <div className="fullscreen-state">
        <StateView loading>{t("loading")}</StateView>
      </div>
    );
  if (status !== "authenticated")
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

export function App() {
  const setStatus = useAuth((state) => state.setStatus);
  useEffect(() => {
    void bootstrapAuth().then((ok) => {
      if (!ok) setStatus("anonymous");
    });
  }, [setStatus]);
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPage />} />
      <Route path="/verify-email" element={<TokenPage kind="verify" />} />
      <Route path="/reset-password" element={<TokenPage kind="reset" />} />
      <Route
        path="/worlds"
        element={
          <Protected>
            <WorldPage />
          </Protected>
        }
      />
      <Route
        path="/tutorial"
        element={
          <Protected>
            <TutorialPage />
          </Protected>
        }
      />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/command" element={<DashboardPage />} />
        <Route path="/city" element={<CityPage />} />
        <Route path="/city/:districtId" element={<CityPage />} />
        <Route path="/germany" element={<GermanyPage />} />
        <Route path="/companies" element={<BusinessesPage />} />
        <Route path="/companies/:companyId" element={<BusinessesPage />} />
        <Route path="/exchange" element={<ExchangePage />} />
        <Route path="/exchange/:listingId" element={<ExchangePage />} />
        <Route
          path="/businesses"
          element={<Navigate to="/companies" replace />}
        />
        <Route path="/businesses/:businessId" element={<BusinessesPage />} />
        <Route path="/facilities" element={<FacilitiesPage />} />
        <Route path="/specialists" element={<SpecialistsPage />} />
        <Route
          path="/specialists/:specialistId"
          element={<SpecialistsPage />}
        />
        <Route path="/operations" element={<OperationsPage />} />
        <Route path="/operations/:operationId" element={<OperationsPage />} />
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/intelligence" element={<IntelligencePage />} />
        <Route path="/investigation" element={<InvestigationPage />} />
        <Route path="/cartels" element={<CartelsPage />} />
        <Route path="/cartels/:cartelId/*" element={<CartelsPage />} />
        <Route
          path="/organizations/*"
          element={<Navigate to="/cartels" replace />}
        />
        <Route path="/diplomacy" element={<DiplomacyPage />} />
        <Route path="/pvp" element={<PvpPage />} />
        <Route path="/territories" element={<TerritoriesPage />} />
        <Route path="/wars" element={<WarsPage />} />
        <Route path="/alliances" element={<AlliancesPage />} />
        <Route path="/communications" element={<CommunicationsPage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/finance" element={<FinancePage />} />
        <Route path="/bonds" element={<BondsPage />} />
        <Route path="/real-estate" element={<RealEstatePage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/rankings" element={<RankingsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/moderation" element={<ModerationPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
