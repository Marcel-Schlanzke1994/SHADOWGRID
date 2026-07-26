import { useState } from "react";
import { useTranslation } from "react-i18next";
import { GlobalDayNightBackdrop } from "../GlobalBackdrop";
import { Panel } from "../components";

const themes = ["day", "night", "neutral"] as const;
const heatmaps = [
  "economy",
  "information",
  "authority",
  "organization",
  "event",
] as const;
const mapLayers = [
  ["map-germany-outline-v1.svg", "germanyMapLayerOutline"],
  ["map-coasts-water-v1.svg", "germanyMapLayerWater"],
  ["map-major-rivers-v1.svg", "germanyMapLayerRivers"],
  ["map-federal-state-borders-v1.svg", "germanyMapLayerStates"],
] as const;
const intensityKeys = [
  "germanyMapIntensityVeryLow",
  "germanyMapIntensityLow",
  "germanyMapIntensityMedium",
  "germanyMapIntensityHigh",
  "germanyMapIntensityVeryHigh",
] as const;
const markerGroups = [
  {
    title: "germanyMapMarkerCities",
    entries: [
      ["marker-metropolis-v1.svg", "germanyMapMarkerMetropolis"],
      ["marker-large-city-v1.svg", "germanyMapMarkerLargeCity"],
      ["marker-medium-city-v1.svg", "germanyMapMarkerMediumCity"],
      ["marker-small-town-v1.svg", "germanyMapMarkerSmallTown"],
      ["marker-home-city-v1.svg", "germanyMapMarkerHomeCity"],
      [
        "marker-cartel-headquarters-v1.svg",
        "germanyMapMarkerOrganizationHeadquarters",
      ],
      ["marker-contested-city-v1.svg", "germanyMapMarkerContestedCity"],
      ["marker-seasonal-event-v1.svg", "germanyMapMarkerSeasonalEvent"],
    ],
  },
  {
    title: "germanyMapMarkerInfluence",
    entries: [
      ["marker-influence-economy-v1.svg", "germanyMapMarkerEconomy"],
      ["marker-influence-street-v1.svg", "germanyMapMarkerStreet"],
      ["marker-influence-information-v1.svg", "germanyMapMarkerInformation"],
      ["marker-influence-society-v1.svg", "germanyMapMarkerSociety"],
      ["marker-influence-digital-v1.svg", "germanyMapMarkerDigital"],
    ],
  },
  {
    title: "germanyMapMarkerControlPoints",
    entries: [
      [
        "marker-control-economic-network-v1.svg",
        "germanyMapMarkerEconomicNetwork",
      ],
      [
        "marker-control-information-center-v1.svg",
        "germanyMapMarkerInformationCenter",
      ],
      ["marker-control-logistics-node-v1.svg", "germanyMapMarkerLogisticsNode"],
      ["marker-control-social-access-v1.svg", "germanyMapMarkerSocialAccess"],
      ["marker-control-digital-node-v1.svg", "germanyMapMarkerDigitalNode"],
      [
        "marker-control-coordination-center-v1.svg",
        "germanyMapMarkerCoordinationCenter",
      ],
    ],
  },
] as const;
const cityPackages = [
  {
    slug: "koeln",
    title: "germanyMapCityKoeln",
    description: "germanyMapCityKoelnDescription",
    heroAlt: "germanyMapCityKoelnHeroAlt",
    cardAlt: "germanyMapCityKoelnCardAlt",
  },
  {
    slug: "hamburg",
    title: "germanyMapCityHamburg",
    description: "germanyMapCityHamburgDescription",
    heroAlt: "germanyMapCityHamburgHeroAlt",
    cardAlt: "germanyMapCityHamburgCardAlt",
  },
  {
    slug: "berlin",
    title: "germanyMapCityBerlin",
    description: "germanyMapCityBerlinDescription",
    heroAlt: "germanyMapCityBerlinHeroAlt",
    cardAlt: "germanyMapCityBerlinCardAlt",
  },
  {
    slug: "muenchen",
    title: "germanyMapCityMuenchen",
    description: "germanyMapCityMuenchenDescription",
    heroAlt: "germanyMapCityMuenchenHeroAlt",
    cardAlt: "germanyMapCityMuenchenCardAlt",
  },
  {
    slug: "frankfurt-am-main",
    title: "germanyMapCityFrankfurt",
    description: "germanyMapCityFrankfurtDescription",
    heroAlt: "germanyMapCityFrankfurtHeroAlt",
    cardAlt: "germanyMapCityFrankfurtCardAlt",
  },
  {
    slug: "duesseldorf",
    title: "germanyMapCityDuesseldorf",
    description: "germanyMapCityDuesseldorfDescription",
    heroAlt: "germanyMapCityDuesseldorfHeroAlt",
    cardAlt: "germanyMapCityDuesseldorfCardAlt",
  },
  {
    slug: "stuttgart",
    title: "germanyMapCityStuttgart",
    description: "germanyMapCityStuttgartDescription",
    heroAlt: "germanyMapCityStuttgartHeroAlt",
    cardAlt: "germanyMapCityStuttgartCardAlt",
  },
] as const;

type Theme = (typeof themes)[number];
type Heatmap = (typeof heatmaps)[number];

const themeKeys: Record<Theme, string> = {
  day: "germanyMapThemeDay",
  night: "germanyMapThemeNight",
  neutral: "germanyMapThemeNeutral",
};
const heatmapKeys: Record<Heatmap, string> = {
  economy: "germanyMapHeatmapEconomy",
  information: "germanyMapHeatmapInformation",
  authority: "germanyMapHeatmapAuthority",
  organization: "germanyMapHeatmapOrganization",
  event: "germanyMapHeatmapEvent",
};

export function GermanyPage() {
  const { t } = useTranslation();
  const [theme, setTheme] = useState<Theme>("night");
  const [heatmap, setHeatmap] = useState<Heatmap>("economy");

  return (
    <div className="page page--germany">
      <GlobalDayNightBackdrop
        dayAssetId="global-germany-map-atmosphere-v1"
        nightAssetId="global-germany-map-atmosphere-v1"
        variant="germany"
      />
      <header className="page-header">
        <h1 id="germany-map-heading">{t("germanyMapTitle")}</h1>
        <p>{t("germanyMapSubtitle")}</p>
      </header>

      <div className="germany-map-toolbar">
        <section aria-labelledby="germany-map-theme-heading">
          <h2 id="germany-map-theme-heading">{t("germanyMapTheme")}</h2>
          <div
            className="layer-switch"
            role="group"
            aria-label={t("germanyMapTheme")}
          >
            {themes.map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={theme === item}
                onClick={() => setTheme(item)}
              >
                {t(themeKeys[item])}
              </button>
            ))}
          </div>
        </section>
        <section aria-labelledby="germany-map-heatmap-heading">
          <h2 id="germany-map-heatmap-heading">{t("germanyMapLegend")}</h2>
          <div
            className="layer-switch"
            role="group"
            aria-label={t("germanyMapLegend")}
          >
            {heatmaps.map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={heatmap === item}
                onClick={() => setHeatmap(item)}
              >
                {t(heatmapKeys[item])}
              </button>
            ))}
          </div>
        </section>
      </div>

      <figure className="germany-map-figure">
        <div
          className="germany-map-viewport"
          role="img"
          aria-labelledby="germany-map-heading germany-map-description"
        >
          <span id="germany-map-description" className="sr-only">
            {t("germanyMapDescription")}
          </span>
          <img
            className="germany-map__background"
            src={`/assets/maps/map-map-background-${theme}-v1.svg`}
            alt=""
            aria-hidden="true"
            decoding="async"
          />
          {mapLayers.map(([file]) => (
            <img
              className="germany-map__layer"
              src={`/assets/maps/${file}`}
              alt=""
              aria-hidden="true"
              decoding="async"
              key={file}
            />
          ))}
        </div>
        <figcaption>{t("germanyMapCaption")}</figcaption>
        <div
          className="germany-map-attribution"
          aria-label={t("germanyMapAttribution")}
        >
          <p>
            <a href="https://www.bkg.bund.de" target="_blank" rel="noreferrer">
              {t("germanyMapAttributionVgOwner")}
            </a>{" "}
            <a
              href="https://www.govdata.de/dl-de/by-2-0"
              target="_blank"
              rel="noreferrer"
            >
              {t("germanyMapAttributionLicense")}
            </a>{" "}
            {t("germanyMapAttributionVgSuffix")}{" "}
            <a
              href="https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg_nuts.pdf"
              target="_blank"
              rel="noreferrer"
            >
              {t("germanyMapAttributionSourcesUrl")}
            </a>
          </p>
          <p>
            <a href="https://www.bkg.bund.de" target="_blank" rel="noreferrer">
              {t("germanyMapAttributionDlmOwner")}
            </a>{" "}
            <a
              href="https://www.govdata.de/dl-de/by-2-0"
              target="_blank"
              rel="noreferrer"
            >
              {t("germanyMapAttributionLicense")}
            </a>{" "}
            {t("germanyMapAttributionChanged")}
          </p>
        </div>
      </figure>

      <div className="germany-map-accessibility-grid">
        <Panel title={t("germanyMapSelectedLegend")}>
          <img
            className="germany-map-legend-preview"
            src={`/assets/maps/map-heatmap-${heatmap}-legend-v1.svg`}
            alt=""
            aria-hidden="true"
            decoding="async"
          />
          <ol
            className="germany-map-intensity-list"
            aria-label={t("germanyMapIntensityScale")}
          >
            {intensityKeys.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ol>
        </Panel>
        <Panel title={t("germanyMapAccessibleLayers")}>
          <ul className="germany-map-layer-list">
            {mapLayers.map(([file, key]) => (
              <li key={file}>{t(key)}</li>
            ))}
          </ul>
          <p className="muted">{t("germanyMapReferenceNote")}</p>
        </Panel>
      </div>

      <details className="panel germany-map-marker-catalog">
        <summary>{t("germanyMapMarkerCatalog")}</summary>
        <p className="muted">{t("germanyMapMarkerCatalogDescription")}</p>
        <div className="germany-map-marker-groups">
          {markerGroups.map((group) => (
            <section key={group.title}>
              <h3>{t(group.title)}</h3>
              <ul>
                {group.entries.map(([file, key]) => (
                  <li key={file}>
                    <img
                      src={`/assets/markers/${file}`}
                      alt=""
                      aria-hidden="true"
                      decoding="async"
                    />
                    <span>{t(key)}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </details>

      <details className="panel germany-city-packages">
        <summary>{t("germanyMapCityPackages")}</summary>
        <p className="muted">{t("germanyMapCityPackagesDescription")}</p>
        {cityPackages.map(({ slug, title, description, heroAlt, cardAlt }) => (
          <article className="germany-city-package" key={slug}>
            <h3>{t(title)}</h3>
            <p>{t(description)}</p>
            <figure>
              <picture>
                <source
                  type="image/avif"
                  media="(max-width: 600px) and (prefers-color-scheme: dark)"
                  srcSet={`/assets/cities/city-${slug}-mobile-night-v1-960.avif`}
                />
                <source
                  type="image/avif"
                  media="(max-width: 600px)"
                  srcSet={`/assets/cities/city-${slug}-mobile-day-v1-960.avif`}
                />
                <source
                  type="image/avif"
                  media="(min-width: 1400px) and (prefers-color-scheme: dark)"
                  srcSet={`/assets/cities/city-${slug}-ultrawide-night-v1-1920.avif`}
                />
                <source
                  type="image/avif"
                  media="(min-width: 1400px)"
                  srcSet={`/assets/cities/city-${slug}-ultrawide-day-v1-1920.avif`}
                />
                <source
                  type="image/avif"
                  media="(prefers-color-scheme: dark)"
                  srcSet={`/assets/cities/city-${slug}-desktop-night-v1-1280.avif`}
                />
                <source
                  type="image/avif"
                  srcSet={`/assets/cities/city-${slug}-desktop-day-v1-1280.avif`}
                />
                <img
                  className="germany-city-package__hero"
                  src={`/assets/cities/city-${slug}-desktop-day-v1-1280.png`}
                  alt={t(heroAlt)}
                  decoding="async"
                  loading="lazy"
                />
              </picture>
              <figcaption>{t("germanyMapCityHeroCaption")}</figcaption>
            </figure>
            <div className="germany-city-package__supporting">
              <img
                className="germany-city-package__card"
                src={`/assets/cities/city-${slug}-card-v1-1280.png`}
                alt={t(cardAlt)}
                decoding="async"
                loading="lazy"
              />
              <div className="germany-city-package__silhouette">
                <img
                  src={`/assets/cities/city-${slug}-silhouette-v1.svg`}
                  alt=""
                  aria-hidden="true"
                  decoding="async"
                  loading="lazy"
                />
                <p>{t("germanyMapCitySilhouetteCaption")}</p>
              </div>
            </div>
          </article>
        ))}
      </details>
    </div>
  );
}
