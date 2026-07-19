export type ISODateTime = string;

export interface User {
  id: string;
  email: string;
  display_name: string;
  locale: string;
  email_verified: boolean;
  is_admin: boolean;
  is_moderator: boolean;
}

export interface World {
  id: string;
  slug: string;
  name: string;
  status: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  season_number: number;
}

export interface Resources {
  cash: number;
  capital: number;
  influence: number;
  intelligence: number;
  logistics_capacity: number;
  personnel_capacity: number;
  version: number;
}

export interface Profile {
  id: string;
  world_id: string;
  codename: string;
  archetype: string;
  home_district_id: string | null;
  tutorial_step: number;
  loyalty: number;
  legitimacy: number;
  fear: number;
  investigation_pressure: number;
  stress: number;
  stability: number;
  operation_slots: number;
  protected_until: ISODateTime;
  resources: Resources;
}

export interface District {
  id: string;
  slug: string;
  name: string;
  prosperity: number;
  employment: number;
  safety: number;
  authority_presence: number;
  digital_infrastructure: number;
  property_value: number;
  public_trust: number;
  media_attention: number;
  economic_activity: number;
  social_stability: number;
  map_x: number;
  map_y: number;
  map_points: string;
  influence: Record<string, number>;
}

export interface Business {
  id: string;
  district_id: string;
  business_type: string;
  name: string;
  level: number;
  revenue: number;
  operating_cost: number;
  personnel_need: number;
  logistics_need: number;
  status: string;
  compliance: number;
  reputation: number;
  market_share: number;
  risk: number;
  upgrade_finishes_at: ISODateTime | null;
}

export interface Specialist {
  id: string;
  name: string;
  role: string;
  competence: number;
  loyalty: number;
  ambition: number;
  stress: number;
  exposure: number;
  salary: number;
  status: string;
}

export interface Operation {
  id: string;
  operation_type: string;
  district_id: string;
  specialist_id: string;
  target: string;
  budget: number;
  intelligence_spend: number;
  risk_posture: string;
  secrecy: number;
  status: string;
  result: string | null;
  outcome_json: Record<string, unknown> | null;
  started_at: ISODateTime;
  finishes_at: ISODateTime;
  resolved_at: ISODateTime | null;
}

export interface Organization {
  id: string;
  world_id: string;
  name: string;
  tag: string;
  archetype: string;
  description: string;
  stability: number;
  treasury_cash: number;
  treasury_capital: number;
  member_limit: number;
  my_role: string | null;
  member_count: number;
}

export interface IntelReport {
  id: string;
  title: string;
  summary: string;
  target_type: string;
  target_id: string;
  visible_confidence: number;
  source: string;
  observed_at: ISODateTime;
  expires_at: ISODateTime;
  status: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string; fields?: Record<string, string> };
  server_time: string;
}
