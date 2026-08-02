import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  Company,
  CompanyEconomyReport,
  DividendDeclaration,
  ExchangeConfiguration,
  ExchangeListing,
  ExchangeOrder,
  ExchangeOrderBook,
  ExchangeTrade,
  IpoEligibility,
  PortfolioItem,
  PriceSnapshot,
  Shareholder,
} from "@shadowgrid/shared-types";
import {
  dividendSchema,
  exchangeOrderSchema,
  ipoSchema,
  type DividendInput,
  type ExchangeOrderInput,
  type IpoInput,
} from "@shadowgrid/validation";
import { useEffect, useId, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { client } from "../auth";
import {
  ConfirmDialog,
  Field,
  Metric,
  Panel,
  StateView,
  Status,
} from "../components";
import { formatCents, formatDate, formatNumber } from "../format";
import { GlobalStaticBackdrop } from "../GlobalBackdrop";

const humanize = translateGameValue;

type PendingAction =
  | { kind: "order"; value: ExchangeOrderInput }
  | { kind: "cancel"; order: ExchangeOrder }
  | { kind: "ipo"; value: IpoInput }
  | { kind: "dividend"; value: DividendInput };

function PriceChart({
  snapshots,
  locale,
}: {
  snapshots: PriceSnapshot[];
  locale: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  const chronological = [...snapshots].reverse();
  if (chronological.length === 0) {
    return <p className="state">{t("exchangePriceHistoryEmpty")}</p>;
  }
  const width = 720;
  const height = 230;
  const inset = 28;
  const values = chronological.map((snapshot) => snapshot.price_cents);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = Math.max(1, maximum - minimum);
  const points = chronological
    .map((snapshot, index) => {
      const x =
        chronological.length === 1
          ? width / 2
          : inset +
            (index * (width - inset * 2)) /
              Math.max(1, chronological.length - 1);
      const y =
        inset +
        ((maximum - snapshot.price_cents) * (height - inset * 2)) / range;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <figure className="exchange-chart">
      <figcaption id={`${id}-title`}>{t("exchangePriceHistory")}</figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={`${id}-title ${id}-description`}
      >
        <desc id={`${id}-description`}>
          {chronological
            .map(
              (snapshot) =>
                `${formatDate(snapshot.captured_at, locale)}: ${formatCents(
                  snapshot.price_cents,
                  locale,
                )}`,
            )
            .join(". ")}
        </desc>
        <polyline points={points} />
        {chronological.map((snapshot, index) => {
          const [x = "0", y = "0"] = points.split(" ")[index]?.split(",") ?? [];
          return (
            <circle key={snapshot.id} cx={x} cy={y} r="5" aria-hidden="true" />
          );
        })}
      </svg>
      <div className="exchange-chart__range">
        <span>{formatCents(minimum, locale)}</span>
        <span>{formatCents(maximum, locale)}</span>
      </div>
    </figure>
  );
}

function OrderTable({
  orders,
  locale,
  emptyLabel,
}: {
  orders: ExchangeOrder[];
  locale: string;
  emptyLabel: string;
}) {
  const { t } = useTranslation();
  if (orders.length === 0) return <p className="state">{emptyLabel}</p>;
  return (
    <div className="table-wrap" tabIndex={0}>
      <table>
        <thead>
          <tr>
            <th>{t("exchangeSide")}</th>
            <th>{t("exchangeOrderType")}</th>
            <th>{t("exchangePrice")}</th>
            <th>{t("exchangeRemaining")}</th>
            <th>{t("status")}</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td>{humanize(order.side)}</td>
              <td>{humanize(order.order_type)}</td>
              <td>
                {order.limit_price_cents === null
                  ? t("exchangeMarketPrice")
                  : formatCents(order.limit_price_cents, locale)}
              </td>
              <td>{formatNumber(order.remaining_quantity, locale)}</td>
              <td>
                <Status value={order.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExchangePage() {
  const { t, i18n } = useTranslation();
  const { listingId } = useParams();
  const queryClient = useQueryClient();
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(
    null,
  );
  const [successMessage, setSuccessMessage] = useState("");

  const listings = useQuery({
    queryKey: ["exchange", "listings"],
    queryFn: () => client.get<ExchangeListing[]>("/exchange/listings"),
  });
  const configuration = useQuery({
    queryKey: ["exchange", "configuration"],
    queryFn: () => client.get<ExchangeConfiguration>("/exchange/config"),
  });
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const ownOrders = useQuery({
    queryKey: ["exchange", "orders"],
    queryFn: () => client.get<ExchangeOrder[]>("/exchange/orders/me"),
  });
  const portfolio = useQuery({
    queryKey: ["exchange", "portfolio"],
    queryFn: () => client.get<PortfolioItem[]>("/exchange/portfolio"),
  });
  const selected =
    listings.data?.find((listing) => listing.id === listingId) ??
    listings.data?.[0];
  const selectedId = selected?.id ?? "";

  const orderBook = useQuery({
    queryKey: ["exchange", selectedId, "order-book"],
    queryFn: () =>
      client.get<ExchangeOrderBook>(
        `/exchange/listings/${selectedId}/order-book`,
      ),
    enabled: Boolean(selectedId),
  });
  const trades = useQuery({
    queryKey: ["exchange", selectedId, "trades"],
    queryFn: () =>
      client.get<ExchangeTrade[]>(`/exchange/listings/${selectedId}/trades`),
    enabled: Boolean(selectedId),
  });
  const prices = useQuery({
    queryKey: ["exchange", selectedId, "prices"],
    queryFn: () =>
      client.get<PriceSnapshot[]>(`/exchange/listings/${selectedId}/prices`),
    enabled: Boolean(selectedId),
  });
  const reports = useQuery({
    queryKey: ["exchange", selectedId, "reports"],
    queryFn: () =>
      client.get<CompanyEconomyReport[]>(
        `/exchange/listings/${selectedId}/reports`,
      ),
    enabled: Boolean(selectedId),
  });
  const shareholders = useQuery({
    queryKey: ["exchange", selectedId, "shareholders"],
    queryFn: () =>
      client.get<Shareholder[]>(
        `/exchange/listings/${selectedId}/shareholders`,
      ),
    enabled: Boolean(selectedId),
  });
  const dividends = useQuery({
    queryKey: ["exchange", selectedId, "dividends"],
    queryFn: () =>
      client.get<DividendDeclaration[]>(
        `/exchange/listings/${selectedId}/dividends`,
      ),
    enabled: Boolean(selectedId),
  });

  const privateCompanies = useMemo(
    () =>
      companies.data?.filter((company) => company.status === "private") ?? [],
    [companies.data],
  );
  const orderForm = useForm<ExchangeOrderInput>({
    resolver: zodResolver(exchangeOrderSchema),
    shouldUnregister: true,
    defaultValues: {
      listing_id: selectedId,
      side: "buy",
      order_type: "limit",
      quantity: 1,
      limit_price_cents: selected?.last_price_cents,
      expires_at: "",
    },
  });
  const ipoForm = useForm<IpoInput>({
    resolver: zodResolver(ipoSchema),
    defaultValues: {
      company_id: privateCompanies[0]?.id ?? "",
      symbol: "",
      total_shares: 100_000,
      offered_shares: 20_000,
    },
  });
  const dividendForm = useForm<DividendInput>({
    resolver: zodResolver(dividendSchema),
    defaultValues: {
      company_id: selected?.company_id ?? "",
      per_share_cents: 1,
    },
  });
  const orderType = orderForm.watch("order_type");
  const ipoCompanyId = ipoForm.watch("company_id");
  const eligibility = useQuery({
    queryKey: ["exchange", "ipo-eligibility", ipoCompanyId],
    queryFn: () =>
      client.get<IpoEligibility>(`/companies/${ipoCompanyId}/ipo-eligibility`),
    enabled: Boolean(ipoCompanyId),
  });

  useEffect(() => {
    if (!selected) return;
    orderForm.setValue("listing_id", selected.id);
    orderForm.setValue("limit_price_cents", selected.last_price_cents);
    dividendForm.setValue("company_id", selected.company_id);
  }, [dividendForm, orderForm, selected]);
  useEffect(() => {
    if (!ipoForm.getValues("company_id") && privateCompanies[0]) {
      ipoForm.setValue("company_id", privateCompanies[0].id);
    }
  }, [ipoForm, privateCompanies]);

  const refreshExchange = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["exchange"] }),
      queryClient.invalidateQueries({ queryKey: ["companies"] }),
    ]);
  };
  const orderMutation = useMutation({
    mutationFn: (value: ExchangeOrderInput) =>
      client.post<ExchangeOrder>(
        "/exchange/orders",
        {
          ...value,
          limit_price_cents:
            value.order_type === "limit" ? value.limit_price_cents : null,
          expires_at: value.expires_at
            ? new Date(value.expires_at).toISOString()
            : null,
        },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("exchangeOrderCreated"));
      orderForm.reset({
        listing_id: selectedId,
        side: "buy",
        order_type: "limit",
        quantity: 1,
        limit_price_cents: selected?.last_price_cents,
        expires_at: "",
      });
      await refreshExchange();
    },
    onError: () => setPendingAction(null),
  });
  const cancelMutation = useMutation({
    mutationFn: (order: ExchangeOrder) =>
      client.delete<ExchangeOrder>(
        `/exchange/orders/${order.id}`,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("exchangeOrderCancelled"));
      await refreshExchange();
    },
    onError: () => setPendingAction(null),
  });
  const ipoMutation = useMutation({
    mutationFn: (value: IpoInput) =>
      client.post<ExchangeListing>(
        `/companies/${value.company_id}/ipo`,
        {
          symbol: value.symbol,
          total_shares: value.total_shares,
          offered_shares: value.offered_shares,
        },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("exchangeIpoCreated"));
      ipoForm.reset({
        company_id: "",
        symbol: "",
        total_shares: 100_000,
        offered_shares: 20_000,
      });
      await refreshExchange();
    },
    onError: () => setPendingAction(null),
  });
  const dividendMutation = useMutation({
    mutationFn: (value: DividendInput) =>
      client.post<DividendDeclaration>(
        `/companies/${value.company_id}/dividends`,
        { per_share_cents: value.per_share_cents },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setSuccessMessage(t("exchangeDividendPaid"));
      dividendForm.setValue("per_share_cents", 1);
      await refreshExchange();
    },
    onError: () => setPendingAction(null),
  });

  const queryError =
    listings.error ??
    configuration.error ??
    companies.error ??
    ownOrders.error ??
    portfolio.error ??
    orderBook.error ??
    trades.error ??
    prices.error ??
    reports.error ??
    shareholders.error ??
    dividends.error ??
    eligibility.error;
  const actionError =
    orderMutation.error ??
    cancelMutation.error ??
    ipoMutation.error ??
    dividendMutation.error;
  const ownedSelectedCompany = companies.data?.some(
    (company) => company.id === selected?.company_id,
  );
  const isPending =
    orderMutation.isPending ||
    cancelMutation.isPending ||
    ipoMutation.isPending ||
    dividendMutation.isPending;

  const confirmAction = () => {
    if (pendingAction?.kind === "order") {
      orderMutation.mutate(pendingAction.value);
    } else if (pendingAction?.kind === "cancel") {
      cancelMutation.mutate(pendingAction.order);
    } else if (pendingAction?.kind === "ipo") {
      ipoMutation.mutate(pendingAction.value);
    } else if (pendingAction?.kind === "dividend") {
      dividendMutation.mutate(pendingAction.value);
    }
  };
  const confirmationDescription = (() => {
    if (pendingAction?.kind === "order") {
      const price =
        pendingAction.value.limit_price_cents ??
        selected?.last_price_cents ??
        0;
      return t("exchangeConfirmOrderDescription", {
        side: humanize(pendingAction.value.side),
        quantity: formatNumber(pendingAction.value.quantity, i18n.language),
        value: formatCents(pendingAction.value.quantity * price, i18n.language),
      });
    }
    if (pendingAction?.kind === "cancel") {
      return t("exchangeConfirmCancelDescription");
    }
    if (pendingAction?.kind === "ipo") {
      return t("exchangeConfirmIpoDescription", {
        fee: formatCents(configuration.data?.ipo_fee_cents ?? 0, i18n.language),
      });
    }
    if (pendingAction?.kind === "dividend") {
      return t("exchangeConfirmDividendDescription", {
        value: formatCents(pendingAction.value.per_share_cents, i18n.language),
      });
    }
    return "";
  })();

  return (
    <div className="page page--exchange">
      <GlobalStaticBackdrop
        assetId="global-exchange-terminal-premium-night-v2"
        variant="exchange"
      />
      <header className="page-header">
        <p className="eyebrow">{t("exchangeEyebrow")}</p>
        <h1>{t("exchangeTitle")}</h1>
        <p>{t("exchangeDescription")}</p>
      </header>
      <StateView
        loading={
          listings.isLoading ||
          configuration.isLoading ||
          companies.isLoading ||
          ownOrders.isLoading ||
          portfolio.isLoading ||
          (Boolean(selectedId) &&
            (orderBook.isLoading ||
              trades.isLoading ||
              prices.isLoading ||
              reports.isLoading ||
              shareholders.isLoading ||
              dividends.isLoading))
        }
        error={queryError}
      >
        {successMessage && (
          <p className="state-success" role="status">
            {successMessage}
          </p>
        )}
        {actionError && (
          <StateView error={actionError}>
            <></>
          </StateView>
        )}

        {listings.data && listings.data.length > 0 && (
          <nav
            className="exchange-market-rail"
            aria-label={t("exchangeListings")}
          >
            {listings.data.slice(0, 4).map((listing) => (
              <Link
                to={`/exchange/${listing.id}`}
                aria-current={selected?.id === listing.id ? "page" : undefined}
                key={listing.id}
              >
                <span className="exchange-market-rail__symbol">
                  {listing.symbol}
                </span>
                <strong>
                  {formatCents(listing.last_price_cents, i18n.language)}
                </strong>
                <Status value={listing.status} />
              </Link>
            ))}
          </nav>
        )}

        <div className="content-grid exchange-overview">
          <Panel title={t("exchangeListings")}>
            {listings.data?.length === 0 && (
              <p className="state">{t("exchangeListingsEmpty")}</p>
            )}
            <div className="card-grid">
              {listings.data?.map((listing) => (
                <Link
                  className={`data-card ${
                    selected?.id === listing.id ? "data-card--selected" : ""
                  }`}
                  to={`/exchange/${listing.id}`}
                  key={listing.id}
                >
                  <span className="eyebrow">{listing.symbol}</span>
                  <h3>{listing.company_name}</h3>
                  <strong>
                    {formatCents(listing.last_price_cents, i18n.language)}
                  </strong>
                  <span>
                    {t("exchangeMarketCapitalization")}:{" "}
                    {formatCents(
                      listing.last_price_cents * listing.total_shares,
                      i18n.language,
                    )}
                  </span>
                  <Status value={listing.status} />
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title={t("exchangeIpo")}>
            {privateCompanies.length === 0 ? (
              <p className="state">{t("exchangeIpoEmpty")}</p>
            ) : (
              <form
                onSubmit={ipoForm.handleSubmit((value) => {
                  setSuccessMessage("");
                  setPendingAction({ kind: "ipo", value });
                })}
              >
                <Field
                  label={t("exchangeCompany")}
                  error={ipoForm.formState.errors.company_id?.message}
                >
                  <select {...ipoForm.register("company_id")}>
                    {privateCompanies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("exchangeSymbol")}
                  error={ipoForm.formState.errors.symbol?.message}
                >
                  <input
                    autoCapitalize="characters"
                    maxLength={8}
                    {...ipoForm.register("symbol")}
                  />
                </Field>
                <Field
                  label={t("exchangeTotalShares")}
                  error={ipoForm.formState.errors.total_shares?.message}
                >
                  <input
                    type="number"
                    min={2}
                    {...ipoForm.register("total_shares", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <Field
                  label={t("exchangeOfferedShares")}
                  error={ipoForm.formState.errors.offered_shares?.message}
                >
                  <input
                    type="number"
                    min={1}
                    {...ipoForm.register("offered_shares", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <div className="exchange-requirements" aria-live="polite">
                  <strong>{t("exchangeIpoEligibility")}</strong>
                  {eligibility.isLoading && <span>{t("loading")}</span>}
                  {eligibility.data?.eligible ? (
                    <Status value={t("exchangeEligible")} />
                  ) : (
                    <ul>
                      {eligibility.data?.reasons.map((reason) => (
                        <li key={reason}>{humanize(reason)}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <p>
                  {t("exchangeIpoFee")}:{" "}
                  {formatCents(
                    configuration.data?.ipo_fee_cents ?? 0,
                    i18n.language,
                  )}
                </p>
                <button
                  className="button"
                  disabled={!eligibility.data?.eligible || isPending}
                >
                  {t("exchangeStartIpo")}
                </button>
              </form>
            )}
          </Panel>
        </div>

        {selected && (
          <>
            <section aria-labelledby="exchange-listing-title">
              <div className="exchange-listing-header">
                <div>
                  <span className="eyebrow">{selected.symbol}</span>
                  <h2 id="exchange-listing-title">{selected.company_name}</h2>
                  <p>{humanize(selected.company_industry)}</p>
                </div>
                <Status value={selected.status} />
              </div>
              <div className="metric-grid">
                <Metric
                  label={t("exchangeLastPrice")}
                  value={formatCents(selected.last_price_cents, i18n.language)}
                />
                <Metric
                  label={t("exchangeMarketCapitalization")}
                  value={formatCents(
                    selected.last_price_cents * selected.total_shares,
                    i18n.language,
                  )}
                />
                <Metric
                  label={t("companyProfit")}
                  value={formatCents(selected.profit_cents, i18n.language)}
                  tone={selected.profit_cents >= 0 ? "good" : "warning"}
                />
                <Metric
                  label={t("exchangeTotalShares")}
                  value={formatNumber(selected.total_shares, i18n.language)}
                />
                <Metric
                  label={t("exchangeDebt")}
                  value={formatCents(selected.debt_cents, i18n.language)}
                />
                <Metric
                  label={t("exchangeListedAt")}
                  value={formatDate(selected.listed_at, i18n.language)}
                />
              </div>
            </section>

            <div className="exchange-detail-grid">
              <Panel title={t("exchangePriceHistory")}>
                <PriceChart
                  snapshots={prices.data ?? []}
                  locale={i18n.language}
                />
              </Panel>
              <Panel title={t("exchangeOrderTicket")}>
                <form
                  onSubmit={orderForm.handleSubmit((value) => {
                    setSuccessMessage("");
                    setPendingAction({ kind: "order", value });
                  })}
                >
                  <input type="hidden" {...orderForm.register("listing_id")} />
                  <Field
                    label={t("exchangeSide")}
                    error={orderForm.formState.errors.side?.message}
                  >
                    <select {...orderForm.register("side")}>
                      <option value="buy">{t("buy")}</option>
                      <option value="sell">{t("exchangeSell")}</option>
                    </select>
                  </Field>
                  <Field
                    label={t("exchangeOrderType")}
                    error={orderForm.formState.errors.order_type?.message}
                  >
                    <select {...orderForm.register("order_type")}>
                      <option value="limit">{t("exchangeLimitOrder")}</option>
                      <option value="market">{t("exchangeMarketOrder")}</option>
                    </select>
                  </Field>
                  <Field
                    label={t("exchangeQuantity")}
                    error={orderForm.formState.errors.quantity?.message}
                  >
                    <input
                      type="number"
                      min={1}
                      {...orderForm.register("quantity", {
                        valueAsNumber: true,
                      })}
                    />
                  </Field>
                  {orderType === "limit" && (
                    <Field
                      label={t("exchangeLimitPrice")}
                      hint={t("exchangeLimitHint", {
                        percent:
                          (configuration.data?.max_price_deviation_bps ?? 0) /
                          100,
                      })}
                      error={
                        orderForm.formState.errors.limit_price_cents?.message
                      }
                    >
                      <input
                        type="number"
                        min={1}
                        {...orderForm.register("limit_price_cents", {
                          valueAsNumber: true,
                        })}
                      />
                    </Field>
                  )}
                  <Field
                    label={t("exchangeExpiry")}
                    hint={t("optional")}
                    error={orderForm.formState.errors.expires_at?.message}
                  >
                    <input
                      type="datetime-local"
                      {...orderForm.register("expires_at")}
                    />
                  </Field>
                  <button className="button" disabled={isPending}>
                    {t("exchangeReviewOrder")}
                  </button>
                </form>
              </Panel>
            </div>

            <div className="exchange-detail-grid">
              <Panel title={t("exchangeOrderBook")}>
                <h3>{t("exchangeBuys")}</h3>
                <OrderTable
                  orders={orderBook.data?.buys ?? []}
                  locale={i18n.language}
                  emptyLabel={t("exchangeBuyBookEmpty")}
                />
                <h3>{t("exchangeSells")}</h3>
                <OrderTable
                  orders={orderBook.data?.sells ?? []}
                  locale={i18n.language}
                  emptyLabel={t("exchangeSellBookEmpty")}
                />
              </Panel>
              <Panel title={t("exchangeRecentTrades")}>
                {trades.data?.length === 0 ? (
                  <p className="state">{t("exchangeTradesEmpty")}</p>
                ) : (
                  <div className="table-wrap" tabIndex={0}>
                    <table>
                      <thead>
                        <tr>
                          <th>{t("date")}</th>
                          <th>{t("exchangePrice")}</th>
                          <th>{t("exchangeQuantity")}</th>
                          <th>{t("exchangeValue")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trades.data?.map((trade) => (
                          <tr key={trade.id}>
                            <td>
                              {formatDate(trade.executed_at, i18n.language)}
                            </td>
                            <td>
                              {formatCents(trade.price_cents, i18n.language)}
                            </td>
                            <td>
                              {formatNumber(trade.quantity, i18n.language)}
                            </td>
                            <td>
                              {formatCents(trade.gross_cents, i18n.language)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            </div>

            <div className="exchange-detail-grid">
              <Panel title={t("exchangeCompanyReports")}>
                {reports.data?.length === 0 ? (
                  <p className="state">{t("economyReportsEmpty")}</p>
                ) : (
                  <div className="table-wrap" tabIndex={0}>
                    <table>
                      <thead>
                        <tr>
                          <th>{t("date")}</th>
                          <th>{t("revenue")}</th>
                          <th>{t("cost")}</th>
                          <th>{t("companyProfit")}</th>
                          <th>{t("marketShare")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reports.data?.map((report) => (
                          <tr key={report.id}>
                            <td>
                              {formatDate(report.created_at, i18n.language)}
                            </td>
                            <td>
                              {formatCents(report.revenue_cents, i18n.language)}
                            </td>
                            <td>
                              {formatCents(report.cost_cents, i18n.language)}
                            </td>
                            <td>
                              {formatCents(report.profit_cents, i18n.language)}
                            </td>
                            <td>{report.market_share_bps / 100}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
              <Panel title={t("exchangeShareholders")}>
                {shareholders.data?.length === 0 ? (
                  <p className="state">{t("exchangeShareholdersEmpty")}</p>
                ) : (
                  <div className="table-wrap" tabIndex={0}>
                    <table>
                      <thead>
                        <tr>
                          <th>{t("codename")}</th>
                          <th>{t("exchangeQuantity")}</th>
                          <th>{t("ownership")}</th>
                          <th>{t("exchangeVotingRights")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shareholders.data?.map((shareholder) => (
                          <tr key={shareholder.holding_id}>
                            <td>{shareholder.codename}</td>
                            <td>
                              {formatNumber(
                                shareholder.quantity,
                                i18n.language,
                              )}
                            </td>
                            <td>{shareholder.ownership_bps / 100}%</td>
                            <td>
                              {formatNumber(
                                shareholder.voting_rights,
                                i18n.language,
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            </div>

            <Panel title={t("exchangeDividends")}>
              {ownedSelectedCompany && (
                <form
                  className="exchange-inline-form"
                  onSubmit={dividendForm.handleSubmit((value) => {
                    setSuccessMessage("");
                    setPendingAction({ kind: "dividend", value });
                  })}
                >
                  <input
                    type="hidden"
                    {...dividendForm.register("company_id")}
                  />
                  <Field
                    label={t("exchangeDividendPerShare")}
                    error={
                      dividendForm.formState.errors.per_share_cents?.message
                    }
                  >
                    <input
                      type="number"
                      min={1}
                      {...dividendForm.register("per_share_cents", {
                        valueAsNumber: true,
                      })}
                    />
                  </Field>
                  <button className="button" disabled={isPending}>
                    {t("exchangeReviewDividend")}
                  </button>
                </form>
              )}
              {dividends.data?.length === 0 ? (
                <p className="state">{t("exchangeDividendsEmpty")}</p>
              ) : (
                <div className="table-wrap" tabIndex={0}>
                  <table>
                    <thead>
                      <tr>
                        <th>{t("date")}</th>
                        <th>{t("exchangeDividendPerShare")}</th>
                        <th>{t("exchangeEligibleShares")}</th>
                        <th>{t("exchangeValue")}</th>
                        <th>{t("status")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dividends.data?.map((dividend) => (
                        <tr key={dividend.id}>
                          <td>{formatDate(dividend.paid_at, i18n.language)}</td>
                          <td>
                            {formatCents(
                              dividend.per_share_cents,
                              i18n.language,
                            )}
                          </td>
                          <td>
                            {formatNumber(
                              dividend.eligible_shares,
                              i18n.language,
                            )}
                          </td>
                          <td>
                            {formatCents(
                              dividend.total_paid_cents,
                              i18n.language,
                            )}
                          </td>
                          <td>
                            <Status value={dividend.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          </>
        )}

        <div className="exchange-detail-grid">
          <Panel title={t("exchangePortfolio")}>
            {portfolio.data?.length === 0 ? (
              <p className="state">{t("exchangePortfolioEmpty")}</p>
            ) : (
              <div className="table-wrap" tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th>{t("exchangeSymbol")}</th>
                      <th>{t("exchangeQuantity")}</th>
                      <th>{t("exchangeAvailable")}</th>
                      <th>{t("exchangeAverageCost")}</th>
                      <th>{t("exchangeMarketValue")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.data?.map((position) => (
                      <tr key={position.holding_id}>
                        <td>
                          <Link to={`/exchange/${position.listing_id}`}>
                            {position.symbol}
                          </Link>
                        </td>
                        <td>
                          {formatNumber(position.quantity, i18n.language)}
                        </td>
                        <td>
                          {formatNumber(
                            position.available_quantity,
                            i18n.language,
                          )}
                        </td>
                        <td>
                          {formatCents(
                            position.average_cost_cents,
                            i18n.language,
                          )}
                        </td>
                        <td>
                          {formatCents(
                            position.market_value_cents,
                            i18n.language,
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel title={t("exchangeOwnOrders")}>
            {ownOrders.data?.length === 0 ? (
              <p className="state">{t("exchangeOwnOrdersEmpty")}</p>
            ) : (
              <div className="table-wrap" tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th>{t("date")}</th>
                      <th>{t("exchangeSide")}</th>
                      <th>{t("exchangeRemaining")}</th>
                      <th>{t("status")}</th>
                      <th>{t("exchangeActions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ownOrders.data?.map((order) => (
                      <tr key={order.id}>
                        <td>{formatDate(order.created_at, i18n.language)}</td>
                        <td>{humanize(order.side)}</td>
                        <td>
                          {formatNumber(
                            order.remaining_quantity,
                            i18n.language,
                          )}
                        </td>
                        <td>
                          <Status value={order.status} />
                        </td>
                        <td>
                          {["open", "partially_filled"].includes(
                            order.status,
                          ) && (
                            <button
                              type="button"
                              className="button button--ghost button--small"
                              onClick={() => {
                                setSuccessMessage("");
                                setPendingAction({ kind: "cancel", order });
                              }}
                            >
                              {t("exchangeCancelOrder")}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </StateView>

      {pendingAction && (
        <ConfirmDialog
          title={t(
            pendingAction.kind === "order"
              ? "exchangeConfirmOrder"
              : pendingAction.kind === "cancel"
                ? "exchangeConfirmCancel"
                : pendingAction.kind === "ipo"
                  ? "exchangeConfirmIpo"
                  : "exchangeConfirmDividend",
          )}
          description={confirmationDescription}
          confirmLabel={t(
            pendingAction.kind === "cancel"
              ? "exchangeCancelOrder"
              : pendingAction.kind === "ipo"
                ? "exchangeStartIpo"
                : pendingAction.kind === "dividend"
                  ? "exchangePayDividend"
                  : "exchangePlaceOrder",
          )}
          cancelLabel={t("cancel")}
          pending={isPending}
          onCancel={() => setPendingAction(null)}
          onConfirm={confirmAction}
        />
      )}
    </div>
  );
}
