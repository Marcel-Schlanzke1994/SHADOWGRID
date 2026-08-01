import { zodResolver } from "@hookform/resolvers/zod";
import { createIdempotencyKey } from "@shadowgrid/api-client";
import { translateGameValue } from "@shadowgrid/i18n";
import type {
  Company,
  PropertyImprovement,
  PropertyLease,
  PropertyTransfer,
  RealEstateConfig,
  RealEstateIndex,
  RealEstateProperty,
} from "@shadowgrid/shared-types";
import {
  propertyAssignmentSchema,
  propertyLeaseSchema,
  propertyListingSchema,
  type PropertyAssignmentInput,
  type PropertyLeaseInput,
  type PropertyListingInput,
} from "@shadowgrid/validation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { client } from "../auth";
import {
  ConfirmDialog,
  Field,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import { formatCents, formatDate, formatNumber } from "../format";

const propertyTypeKeys = {
  land: "propertyTypeLand",
  building: "propertyTypeBuilding",
  commercial_space: "propertyTypeCommercialSpace",
  headquarters: "propertyTypeHeadquarters",
} as const;

export function RealEstatePage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [pendingPurchase, setPendingPurchase] =
    useState<RealEstateProperty | null>(null);
  const [pendingLease, setPendingLease] = useState<PropertyLeaseInput | null>(
    null,
  );
  const [pendingUpgrade, setPendingUpgrade] =
    useState<RealEstateProperty | null>(null);

  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: () => client.get<Company[]>("/companies"),
  });
  const config = useQuery({
    queryKey: ["real-estate-config"],
    queryFn: () => client.get<RealEstateConfig>("/real-estate/config"),
  });
  const indices = useQuery({
    queryKey: ["real-estate-indices"],
    queryFn: () => client.get<RealEstateIndex[]>("/real-estate/indices"),
  });
  const properties = useQuery({
    queryKey: ["real-estate-properties"],
    queryFn: () => client.get<RealEstateProperty[]>("/real-estate/properties"),
  });
  const leases = useQuery({
    queryKey: ["property-leases"],
    queryFn: () => client.get<PropertyLease[]>("/real-estate/leases/me"),
  });

  const manageable = useMemo(
    () =>
      properties.data?.filter(
        (property) =>
          property.is_owned_by_me &&
          property.status === "owned" &&
          property.company_use_id === null,
      ) ?? [],
    [properties.data],
  );
  const assignable = useMemo(
    () => manageable.filter((property) => property.listing_type === null),
    [manageable],
  );
  const rentable = useMemo(
    () =>
      properties.data?.filter(
        (property) =>
          property.status === "owned" && property.listing_type === "rent",
      ) ?? [],
    [properties.data],
  );
  const listingValues = useMemo<PropertyListingInput | undefined>(() => {
    const property = manageable[0];
    if (!property) return undefined;
    return {
      property_id: property.id,
      listing_type: "sale",
      amount_cents: Math.max(1, property.asking_price_cents),
    };
  }, [manageable]);
  const leaseValues = useMemo<PropertyLeaseInput | undefined>(() => {
    const property = rentable[0];
    const company = companies.data?.[0];
    if (!property || !company) return undefined;
    return {
      property_id: property.id,
      tenant_company_id: company.id,
      term_periods: 2,
    };
  }, [companies.data, rentable]);
  const assignmentValues = useMemo<PropertyAssignmentInput | undefined>(() => {
    const property = assignable[0];
    const company = companies.data?.[0];
    if (!property || !company) return undefined;
    return { property_id: property.id, company_id: company.id };
  }, [assignable, companies.data]);
  const listingForm = useForm<PropertyListingInput>({
    resolver: zodResolver(propertyListingSchema),
    values: listingValues,
  });
  const leaseForm = useForm<PropertyLeaseInput>({
    resolver: zodResolver(propertyLeaseSchema),
    values: leaseValues,
  });
  const assignmentForm = useForm<PropertyAssignmentInput>({
    resolver: zodResolver(propertyAssignmentSchema),
    values: assignmentValues,
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["companies"] }),
      queryClient.invalidateQueries({ queryKey: ["real-estate-indices"] }),
      queryClient.invalidateQueries({ queryKey: ["real-estate-properties"] }),
      queryClient.invalidateQueries({ queryKey: ["property-leases"] }),
    ]);
  };
  const purchase = useMutation({
    mutationFn: (property: RealEstateProperty) =>
      client.post<PropertyTransfer>(
        `/real-estate/properties/${property.id}/buy`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("propertyPurchased"));
      setPendingPurchase(null);
      await refresh();
    },
  });
  const listing = useMutation({
    mutationFn: (value: PropertyListingInput) =>
      client.post<RealEstateProperty>(
        `/real-estate/properties/${value.property_id}/list-${value.listing_type}`,
        value.listing_type === "sale"
          ? { asking_price_cents: value.amount_cents }
          : { rent_cents_per_period: value.amount_cents },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("propertyListed"));
      await refresh();
    },
  });
  const startLease = useMutation({
    mutationFn: (value: PropertyLeaseInput) =>
      client.post<PropertyLease>(
        `/real-estate/properties/${value.property_id}/lease`,
        {
          tenant_company_id: value.tenant_company_id,
          term_periods: value.term_periods,
        },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("propertyLeaseStarted"));
      setPendingLease(null);
      await refresh();
    },
  });
  const assign = useMutation({
    mutationFn: (value: PropertyAssignmentInput) =>
      client.post<RealEstateProperty>(
        `/real-estate/properties/${value.property_id}/assign`,
        { company_id: value.company_id },
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("propertyAssigned"));
      await refresh();
    },
  });
  const unassign = useMutation({
    mutationFn: (property: RealEstateProperty) =>
      client.post<RealEstateProperty>(
        `/real-estate/properties/${property.id}/unassign`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("propertyUnassigned"));
      await refresh();
    },
  });
  const upgrade = useMutation({
    mutationFn: (property: RealEstateProperty) =>
      client.post<PropertyImprovement>(
        `/real-estate/properties/${property.id}/headquarters/upgrade`,
        undefined,
        createIdempotencyKey(),
      ),
    onSuccess: async () => {
      setMessage(t("propertyHeadquartersUpgraded"));
      setPendingUpgrade(null);
      await refresh();
    },
  });

  const error =
    companies.error ??
    config.error ??
    indices.error ??
    properties.error ??
    leases.error ??
    purchase.error ??
    listing.error ??
    startLease.error ??
    assign.error ??
    unassign.error ??
    upgrade.error;
  const selectedLeaseProperty = properties.data?.find(
    (property) => property.id === pendingLease?.property_id,
  );
  const selectedLeaseCompany = companies.data?.find(
    (company) => company.id === pendingLease?.tenant_company_id,
  );

  return (
    <div className="page page--real-estate">
      <header className="page-header">
        <h1>{t("realEstateTitle")}</h1>
        <p>{t("realEstateDescription")}</p>
      </header>
      {message && (
        <p className="notice notice--success" role="status">
          {message}
        </p>
      )}
      <StateView
        loading={
          companies.isLoading ||
          config.isLoading ||
          indices.isLoading ||
          properties.isLoading ||
          leases.isLoading
        }
        error={error}
      >
        <Panel title={t("propertyDistrictIndices")}>
          <StateView empty={!indices.data?.length}>
            <div className="card-grid">
              {indices.data?.map((index) => (
                <article className="subcard" key={index.id}>
                  <div className="list-row">
                    <span>
                      <strong>{index.district_name}</strong>
                      <small>{index.city_name}</small>
                    </span>
                    <span>
                      {formatNumber(index.price_index_bps / 100, i18n.language)}
                      %
                    </span>
                  </div>
                  <Progress
                    label={t("propertyDemandIndex", {
                      value: formatNumber(
                        index.demand_bps / 100,
                        i18n.language,
                      ),
                    })}
                    value={Math.min(100, index.demand_bps / 100)}
                  />
                  <small>
                    {t("propertyRentIndex", {
                      value: formatNumber(
                        index.rent_index_bps / 100,
                        i18n.language,
                      ),
                    })}
                  </small>
                </article>
              ))}
            </div>
          </StateView>
        </Panel>

        <Panel title={t("propertyMarket")}>
          <StateView empty={!properties.data?.length}>
            <div className="card-grid">
              {properties.data?.map((property) => (
                <article className="subcard" key={property.id}>
                  <div className="list-row">
                    <span>
                      <strong>{property.name}</strong>
                      <small>
                        {t(propertyTypeKeys[property.property_type])} ·{" "}
                        {property.district_name}
                      </small>
                    </span>
                    <Status value={property.listing_type ?? property.status} />
                  </div>
                  <dl className="detail-list">
                    <div>
                      <dt>{t("propertyOwner")}</dt>
                      <dd>
                        {property.owner_name ?? t("propertyPublicMarket")}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("propertyArea")}</dt>
                      <dd>
                        {formatNumber(property.area_units, i18n.language)}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("propertyMarketValue")}</dt>
                      <dd>
                        {formatCents(
                          property.effective_sale_price_cents,
                          i18n.language,
                        )}
                      </dd>
                    </div>
                    {property.listing_type === "rent" && (
                      <div>
                        <dt>{t("propertyRentPerPeriod")}</dt>
                        <dd>
                          {formatCents(
                            property.effective_rent_cents_per_period,
                            i18n.language,
                          )}
                        </dd>
                      </div>
                    )}
                  </dl>
                  {property.listing_type === "sale" &&
                    !property.is_owned_by_me && (
                      <button
                        className="button button--small"
                        onClick={() => setPendingPurchase(property)}
                      >
                        {t("propertyReviewPurchase")}
                      </button>
                    )}
                  {property.company_use_name && (
                    <p className="notice">
                      {t("propertyUsedBy", {
                        company: property.company_use_name,
                      })}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </StateView>
        </Panel>

        <div className="content-grid">
          <Panel title={t("propertyCreateListing")}>
            <StateView empty={!listingValues}>
              <form
                className="stack"
                onSubmit={listingForm.handleSubmit((value) =>
                  listing.mutate(value),
                )}
              >
                <Field
                  label={t("propertyAsset")}
                  error={listingForm.formState.errors.property_id?.message}
                >
                  <select {...listingForm.register("property_id")}>
                    {manageable.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("propertyListingType")}
                  error={listingForm.formState.errors.listing_type?.message}
                >
                  <select {...listingForm.register("listing_type")}>
                    <option value="sale">{t("propertySale")}</option>
                    <option value="rent">{t("propertyRent")}</option>
                  </select>
                </Field>
                <Field
                  label={t("propertyListingAmount")}
                  error={listingForm.formState.errors.amount_cents?.message}
                >
                  <input
                    type="number"
                    {...listingForm.register("amount_cents", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <button className="button" disabled={listing.isPending}>
                  {t("propertyPublishListing")}
                </button>
              </form>
            </StateView>
          </Panel>

          <Panel title={t("propertyLeaseCompanySpace")}>
            <StateView empty={!leaseValues}>
              <form
                className="stack"
                onSubmit={leaseForm.handleSubmit(setPendingLease)}
              >
                <Field
                  label={t("propertyAsset")}
                  error={leaseForm.formState.errors.property_id?.message}
                >
                  <select {...leaseForm.register("property_id")}>
                    {rentable.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name} ·{" "}
                        {formatCents(
                          property.effective_rent_cents_per_period,
                          i18n.language,
                        )}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("propertyTenantCompany")}
                  error={leaseForm.formState.errors.tenant_company_id?.message}
                >
                  <select {...leaseForm.register("tenant_company_id")}>
                    {companies.data?.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("propertyLeaseTerm")}
                  error={leaseForm.formState.errors.term_periods?.message}
                >
                  <input
                    type="number"
                    max={config.data?.max_lease_periods}
                    {...leaseForm.register("term_periods", {
                      valueAsNumber: true,
                    })}
                  />
                </Field>
                <button className="button">{t("propertyReviewLease")}</button>
              </form>
            </StateView>
          </Panel>

          <Panel title={t("propertyCompanyUse")}>
            <StateView empty={!assignmentValues}>
              <form
                className="stack"
                onSubmit={assignmentForm.handleSubmit((value) =>
                  assign.mutate(value),
                )}
              >
                <Field
                  label={t("propertyAsset")}
                  error={assignmentForm.formState.errors.property_id?.message}
                >
                  <select {...assignmentForm.register("property_id")}>
                    {assignable.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label={t("propertyCompany")}
                  error={assignmentForm.formState.errors.company_id?.message}
                >
                  <select {...assignmentForm.register("company_id")}>
                    {companies.data?.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <button className="button" disabled={assign.isPending}>
                  {t("propertyAssign")}
                </button>
              </form>
            </StateView>
          </Panel>
        </div>

        <Panel title={t("propertyPortfolio")}>
          <StateView
            empty={
              !properties.data?.some((property) => property.is_owned_by_me)
            }
          >
            <div className="stack">
              {properties.data
                ?.filter((property) => property.is_owned_by_me)
                .map((property) => (
                  <article className="subcard" key={property.id}>
                    <div className="list-row">
                      <span>
                        <strong>{property.name}</strong>
                        <small>
                          {t(propertyTypeKeys[property.property_type])} ·{" "}
                          {t("propertyHeadquartersLevel", {
                            level: property.headquarters_level,
                          })}
                        </small>
                      </span>
                      <Status value={property.status} />
                    </div>
                    <div className="button-row">
                      {property.status === "owned" &&
                        property.company_use_id && (
                          <button
                            className="button button--ghost button--small"
                            disabled={unassign.isPending}
                            onClick={() => unassign.mutate(property)}
                          >
                            {t("propertyUnassign")}
                          </button>
                        )}
                      {property.property_type === "headquarters" &&
                        property.company_use_id &&
                        property.headquarters_level < 10 && (
                          <button
                            className="button button--small"
                            onClick={() => setPendingUpgrade(property)}
                          >
                            {t("propertyReviewHeadquartersUpgrade")}
                          </button>
                        )}
                    </div>
                  </article>
                ))}
            </div>
          </StateView>
        </Panel>

        <Panel title={t("propertyLeaseHistory")}>
          <StateView empty={!leases.data?.length}>
            <div className="stack">
              {leases.data?.map((lease) => (
                <article className="subcard" key={lease.id}>
                  <div className="list-row">
                    <span>
                      <strong>{lease.property_name}</strong>
                      <small>
                        {lease.tenant_company_name} · {lease.landlord_name}
                      </small>
                    </span>
                    <Status value={lease.status} />
                  </div>
                  <Progress
                    label={t("propertyLeaseProgress", {
                      paid: lease.periods_paid,
                      total: lease.term_periods,
                    })}
                    value={(lease.periods_paid * 100) / lease.term_periods}
                  />
                  <small>
                    {t("propertyLeaseEnds", {
                      date: formatDate(lease.ends_at, i18n.language),
                    })}
                  </small>
                  {lease.default_reason && (
                    <p className="notice notice--warning">
                      {t("propertyAbstractDefault", {
                        reason: translateGameValue(lease.default_reason),
                      })}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </StateView>
        </Panel>
      </StateView>

      {pendingPurchase && (
        <ConfirmDialog
          title={t("propertyConfirmPurchase")}
          description={t("propertyConfirmPurchaseDescription", {
            property: pendingPurchase.name,
            amount: formatCents(
              pendingPurchase.effective_sale_price_cents,
              i18n.language,
            ),
          })}
          confirmLabel={t("propertyBuy")}
          cancelLabel={t("cancel")}
          pending={purchase.isPending}
          onCancel={() => setPendingPurchase(null)}
          onConfirm={() => purchase.mutate(pendingPurchase)}
        />
      )}
      {pendingLease && selectedLeaseProperty && selectedLeaseCompany && (
        <ConfirmDialog
          title={t("propertyConfirmLease")}
          description={t("propertyConfirmLeaseDescription", {
            property: selectedLeaseProperty.name,
            company: selectedLeaseCompany.name,
            amount: formatCents(
              selectedLeaseProperty.effective_rent_cents_per_period,
              i18n.language,
            ),
            periods: pendingLease.term_periods,
          })}
          confirmLabel={t("propertyLease")}
          cancelLabel={t("cancel")}
          pending={startLease.isPending}
          onCancel={() => setPendingLease(null)}
          onConfirm={() => startLease.mutate(pendingLease)}
        />
      )}
      {pendingUpgrade && (
        <ConfirmDialog
          title={t("propertyConfirmHeadquartersUpgrade")}
          description={t("propertyConfirmHeadquartersUpgradeDescription", {
            property: pendingUpgrade.name,
            level: pendingUpgrade.headquarters_level + 1,
          })}
          confirmLabel={t("propertyUpgrade")}
          cancelLabel={t("cancel")}
          pending={upgrade.isPending}
          onCancel={() => setPendingUpgrade(null)}
          onConfirm={() => upgrade.mutate(pendingUpgrade)}
        />
      )}
    </div>
  );
}
