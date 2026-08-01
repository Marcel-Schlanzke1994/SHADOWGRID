import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  totp_code: z
    .string()
    .regex(/^\d{6}$/)
    .optional(),
});
export const registerSchema = z.object({
  email: z.string().email(),
  display_name: z.string().min(2).max(40),
  password: z
    .string()
    .min(12)
    .max(128)
    .regex(/[a-z]/)
    .regex(/[A-Z]/)
    .regex(/\d/),
  terms_accepted: z.literal(true),
});
export const operationSchema = z.object({
  operation_type: z.string(),
  district_id: z.string().uuid(),
  specialist_id: z.string().uuid(),
  target: z.string().min(2).max(120),
  budget: z.number().min(1000).max(1_000_000),
  intelligence_spend: z.number().min(0).max(100),
  risk_posture: z.enum(["cautious", "balanced", "aggressive"]),
  secrecy: z.number().min(0).max(100),
});

export const exchangeOrderSchema = z
  .object({
    listing_id: z.string().uuid(),
    side: z.enum(["buy", "sell"]),
    order_type: z.enum(["market", "limit"]),
    quantity: z.number().int().min(1).max(100_000_000_000),
    limit_price_cents: z.number().int().min(1).max(100_000_000_000).optional(),
    expires_at: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (value.order_type === "limit" && value.limit_price_cents === undefined) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["limit_price_cents"],
        message: "A limit price is required.",
      });
    }
    if (
      value.order_type === "market" &&
      value.limit_price_cents !== undefined
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["limit_price_cents"],
        message: "Market orders cannot define a limit price.",
      });
    }
  });

export const ipoSchema = z
  .object({
    company_id: z.string().uuid(),
    symbol: z
      .string()
      .trim()
      .min(2)
      .max(8)
      .regex(/^[A-Za-z0-9]+$/),
    total_shares: z.number().int().min(2).max(100_000_000_000),
    offered_shares: z.number().int().min(1).max(100_000_000_000),
  })
  .refine((value) => value.offered_shares < value.total_shares, {
    path: ["offered_shares"],
    message: "Offered shares must be lower than total shares.",
  });

export const dividendSchema = z.object({
  company_id: z.string().uuid(),
  per_share_cents: z.number().int().min(1).max(1_000_000_000),
});

export type ExchangeOrderInput = z.infer<typeof exchangeOrderSchema>;
export type IpoInput = z.infer<typeof ipoSchema>;
export type DividendInput = z.infer<typeof dividendSchema>;

export const cartelCreateSchema = z.object({
  name: z.string().trim().min(3).max(80),
  tag: z
    .string()
    .trim()
    .min(2)
    .max(8)
    .regex(/^[A-Za-z0-9]+$/),
  archetype: z.string().min(1),
  description: z.string().max(500),
  governance_model: z.enum([
    "directorate",
    "council",
    "federation",
    "collective",
  ]),
});

export const cartelInvitationSchema = z.object({
  email: z.string().email(),
});

export const cartelTreasuryDepositSchema = z.object({
  amount_cents: z.number().int().min(1).max(1_000_000_000),
});

export const cartelExpenseSchema = z.object({
  amount_cents: z.number().int().min(1).max(10_000_000_000),
  purpose: z.string().trim().min(3).max(240),
});

export const cartelProjectSchema = z.object({
  project_type: z.enum([
    "logistics_hub",
    "technology_center",
    "media_campaign",
    "compliance_network",
    "trade_center",
  ]),
  district_id: z.string().uuid(),
});

export const cartelContributionSchema = z.object({
  resource_type: z.enum(["cash", "influence", "intelligence"]),
  amount_units: z.number().int().min(1).max(1_000_000_000),
});

export type CartelCreateInput = z.infer<typeof cartelCreateSchema>;
export type CartelInvitationInput = z.infer<typeof cartelInvitationSchema>;
export type CartelTreasuryDepositInput = z.infer<
  typeof cartelTreasuryDepositSchema
>;
export type CartelExpenseInput = z.infer<typeof cartelExpenseSchema>;
export type CartelProjectInput = z.infer<typeof cartelProjectSchema>;
export type CartelContributionInput = z.infer<typeof cartelContributionSchema>;

export const intelligenceOperationSchema = z.object({
  target_profile_id: z.string().uuid(),
  specialist_id: z.string().uuid(),
  information_type: z.enum(["public", "analyzed", "covert"]),
  category: z.enum([
    "economy",
    "companies",
    "exchange",
    "cartel",
    "territory",
    "specialists",
    "reputation",
  ]),
});

export const intelligenceOfferSchema = z.object({
  price_cents: z.number().int().min(1).max(1_000_000_000),
  expires_in_hours: z.number().int().min(1).max(168),
});

export const strategicActionSchema = z.object({
  target_profile_id: z.string().uuid(),
  specialist_id: z.string().uuid(),
  action_type: z.enum([
    "delay_project",
    "weaken_reputation",
    "raise_operating_cost",
    "make_information_unreliable",
    "stress_specialist",
  ]),
  target_id: z.string().uuid().optional(),
});

export type IntelligenceOperationInput = z.infer<
  typeof intelligenceOperationSchema
>;
export type IntelligenceOfferInput = z.infer<typeof intelligenceOfferSchema>;
export type StrategicActionInput = z.infer<typeof strategicActionSchema>;

export const worldEventPlanSchema = z.object({
  event_key: z.string().min(2).max(60),
  scope_type: z.enum(["world", "city", "district", "industry", "company"]),
  scope_id: z.string().max(60).optional(),
  starts_at: z.string().min(1),
  duration_minutes: z.number().int().min(1).max(43_200),
  revenue_multiplier_bps: z.number().int().min(2_500).max(30_000).optional(),
  cost_multiplier_bps: z.number().int().min(2_500).max(30_000).optional(),
  demand_multiplier_bps: z.number().int().min(2_500).max(30_000).optional(),
});

export type WorldEventPlanInput = z.infer<typeof worldEventPlanSchema>;

export const seasonAdminSchema = z.object({
  duration_minutes: z.number().int().min(5).max(201_600),
  simulate_at: z.string().min(1),
});

export type SeasonAdminInput = z.infer<typeof seasonAdminSchema>;

export const contractTenderSchema = z.object({
  issuer_company_id: z.string().uuid(),
  contract_type: z.enum(["supply", "service"]),
  title: z.string().trim().min(3).max(140),
  description: z.string().trim().max(500),
  max_price_cents: z.number().int().min(1).max(100_000_000_000),
  duration_periods: z.number().int().min(1).max(720),
  capacity_units: z.number().int().min(1).max(10_000),
  min_reputation_bps: z.number().int().min(0).max(10_000),
  min_compliance_bps: z.number().int().min(0).max(10_000),
  submission_minutes: z.number().int().min(5).max(10_080),
});

export const contractBidSchema = z.object({
  tender_id: z.string().uuid(),
  bidder_company_id: z.string().uuid(),
  price_cents: z.number().int().min(1).max(100_000_000_000),
});

export type ContractTenderInput = z.infer<typeof contractTenderSchema>;
export type ContractBidInput = z.infer<typeof contractBidSchema>;

export const loanApplicationSchema = z.object({
  company_id: z.string().uuid(),
  requested_principal_cents: z.number().int().min(100_000).max(100_000_000_000),
  term_periods: z.number().int().min(1).max(720),
  collateral_score_bps: z.number().int().min(0).max(10_000),
  purpose: z.string().trim().min(3).max(240),
});

export type LoanApplicationInput = z.infer<typeof loanApplicationSchema>;

export const bondIssueSchema = z.object({
  issuer_company_id: z.string().uuid(),
  symbol: z
    .string()
    .trim()
    .min(2)
    .max(12)
    .regex(/^[A-Za-z0-9]+$/),
  title: z.string().trim().min(3).max(140),
  face_value_cents: z.number().int().min(1).max(100_000_000_000),
  total_units: z.number().int().min(1).max(1_000_000),
  coupon_rate_bps: z.number().int().min(1).max(20_000),
  term_periods: z.number().int().min(1).max(720),
});

export const bondSubscriptionSchema = z.object({
  issue_id: z.string().uuid(),
  quantity: z.number().int().min(1).max(1_000_000),
});

export type BondIssueInput = z.infer<typeof bondIssueSchema>;
export type BondSubscriptionInput = z.infer<typeof bondSubscriptionSchema>;

export const propertyListingSchema = z.object({
  property_id: z.string().uuid(),
  listing_type: z.enum(["sale", "rent"]),
  amount_cents: z.number().int().min(1).max(100_000_000_000),
});

export const propertyLeaseSchema = z.object({
  property_id: z.string().uuid(),
  tenant_company_id: z.string().uuid(),
  term_periods: z.number().int().min(2).max(720),
});

export const propertyAssignmentSchema = z.object({
  property_id: z.string().uuid(),
  company_id: z.string().uuid(),
});

export type PropertyListingInput = z.infer<typeof propertyListingSchema>;
export type PropertyLeaseInput = z.infer<typeof propertyLeaseSchema>;
export type PropertyAssignmentInput = z.infer<
  typeof propertyAssignmentSchema
>;
