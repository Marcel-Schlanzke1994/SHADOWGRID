const globalAssetWidths = [320, 640, 960, 1280, 1920, 2560, 3840];

const globalAssetSrcSet = (assetId: string, format: "avif" | "webp") =>
  globalAssetWidths
    .map((width) => `/assets/global/${assetId}-${width}.${format} ${width}w`)
    .join(", ");

export function GlobalBackdrop({
  desktopAssetId,
  mobileAssetId,
  variant,
}: {
  desktopAssetId: string;
  mobileAssetId: string;
  variant: "auth" | "world";
}) {
  return (
    <>
      <picture
        className={`scene-backdrop scene-backdrop--${variant}`}
        aria-hidden="true"
      >
        <source
          type="image/avif"
          media="(max-width: 600px)"
          srcSet={globalAssetSrcSet(mobileAssetId, "avif")}
          sizes="100vw"
        />
        <source
          type="image/avif"
          srcSet={globalAssetSrcSet(desktopAssetId, "avif")}
          sizes="100vw"
        />
        <source
          type="image/webp"
          media="(max-width: 600px)"
          srcSet={globalAssetSrcSet(mobileAssetId, "webp")}
          sizes="100vw"
        />
        <source
          type="image/webp"
          srcSet={globalAssetSrcSet(desktopAssetId, "webp")}
          sizes="100vw"
        />
        <source
          type="image/png"
          media="(max-width: 600px)"
          srcSet={`/assets/global/${mobileAssetId}-1152.png`}
        />
        <img
          src={`/assets/global/${desktopAssetId}-1280.png`}
          alt=""
          decoding="async"
        />
      </picture>
      <div
        className={`scene-backdrop__shade scene-backdrop__shade--${variant}`}
        aria-hidden="true"
      />
    </>
  );
}

export function GlobalDayNightBackdrop({
  dayAssetId,
  nightAssetId,
  variant,
}: {
  dayAssetId: string;
  nightAssetId: string;
  variant: "command" | "germany";
}) {
  return (
    <>
      <picture
        className={`day-night-backdrop day-night-backdrop--${variant}`}
        aria-hidden="true"
      >
        <source
          type="image/avif"
          media="(prefers-color-scheme: dark)"
          srcSet={globalAssetSrcSet(nightAssetId, "avif")}
          sizes="100vw"
        />
        <source
          type="image/avif"
          srcSet={globalAssetSrcSet(dayAssetId, "avif")}
          sizes="100vw"
        />
        <source
          type="image/webp"
          media="(prefers-color-scheme: dark)"
          srcSet={globalAssetSrcSet(nightAssetId, "webp")}
          sizes="100vw"
        />
        <source
          type="image/webp"
          srcSet={globalAssetSrcSet(dayAssetId, "webp")}
          sizes="100vw"
        />
        <source
          type="image/png"
          media="(prefers-color-scheme: dark)"
          srcSet={`/assets/global/${nightAssetId}-1280.png`}
        />
        <img
          src={`/assets/global/${dayAssetId}-1280.png`}
          alt=""
          decoding="async"
        />
      </picture>
      <div
        className={`day-night-backdrop__shade day-night-backdrop__shade--${variant}`}
        aria-hidden="true"
      />
    </>
  );
}

export function GlobalStateBackdrop({
  assetId,
  variant,
}: {
  assetId: string;
  variant: "offline" | "maintenance" | "season-complete";
}) {
  return (
    <>
      <picture
        className={`system-state-backdrop system-state-backdrop--${variant}`}
        aria-hidden="true"
      >
        <source
          type="image/avif"
          srcSet={globalAssetSrcSet(assetId, "avif")}
          sizes="100vw"
        />
        <source
          type="image/webp"
          srcSet={globalAssetSrcSet(assetId, "webp")}
          sizes="100vw"
        />
        <img
          src={`/assets/global/${assetId}-1280.png`}
          alt=""
          decoding="async"
        />
      </picture>
      <div
        className={`system-state-backdrop__shade system-state-backdrop__shade--${variant}`}
        aria-hidden="true"
      />
    </>
  );
}
