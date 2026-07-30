from __future__ import annotations

from decimal import Decimal
from typing import Final, TypedDict


class ResearchDefinition(TypedDict):
    category: str
    cash: int
    capital: int
    minutes: int


class CartelProjectTemplate(TypedDict):
    title: str
    cash_cents: int
    influence: int
    intelligence: int
    duration_hours: int
    influence_kind: str
    influence_reward: int


class CompanyIndustryDefinition(TypedDict):
    enterprise_value_cents: int
    revenue_cents: int
    cost_cents: int
    employees: int
    capacity: int
    quality: int
    market_share_bps: int
    reputation_bps: int
    compliance_bps: int
    innovation_bps: int
    risk_bps: int


class CompanyInvestmentDefinition(TypedDict):
    cost_cents: int
    metric: str
    increase: int


class EconomyMarketDefinition(TypedDict):
    demand_units: int
    unit_revenue_cents: int
    variable_cost_per_unit_cents: int
    fixed_cost_cents: int


class SpecialistRoleDefinition(TypedDict):
    base_salary_cents: int
    primary_skill: str
    effect: str


class WorldEventTemplateDefinition(TypedDict):
    title: str
    description: str
    default_scope_type: str
    default_duration_minutes: int
    effects: dict[str, int]


class SeasonTemplateDefinition(TypedDict):
    name: str
    phase_weights_bps: dict[str, int]
    goals: list[dict[str, str | int]]
    scoring_categories: tuple[str, ...]


START_RESOURCES: Final = {
    "capital": 25_000,
    "influence": 10,
    "intelligence": 15,
    "logistics_capacity": 10,
    "personnel_capacity": 8,
}

WORLD_SLUG: Final = "germany-season-0"
WORLD_NAME: Final = "Deutschland — Saison 0"
START_CITY: Final = {
    "slug": "koeln",
    "name": "Köln",
    "region_key": "nordrhein-westfalen",
    "instance_key": "koeln-1",
}

ARCHETYPES: Final = {
    "family_network": {
        "loyalty": 10,
        "recruitment_speed": -10,
        "personal_conflict_impact": 10,
    },
    "street_alliance": {"street_presence": 15, "visibility": 10, "loyalty": -8},
    "business_consortium": {"business_revenue": 10, "legitimacy": 10, "financial_risk": 8},
    "cyber_collective": {
        "intelligence_gain": 15,
        "digital_influence": 15,
        "physical_presence": -10,
    },
}

DISTRICTS: Final = (
    (
        "innenstadt",
        "Innenstadt",
        85,
        82,
        74,
        86,
        92,
        88,
        70,
        66,
        91,
        78,
        70,
        8,
        "6,14 30,7 43,23 31,42 8,37",
    ),
    (
        "hafenbezirk",
        "Hafenbezirk",
        56,
        68,
        52,
        78,
        61,
        48,
        45,
        58,
        78,
        54,
        16,
        43,
        "8,42 32,43 38,60 18,74 5,61",
    ),
    (
        "technologiepark",
        "Technologiepark",
        72,
        70,
        48,
        64,
        83,
        76,
        58,
        82,
        85,
        57,
        43,
        24,
        "44,18 68,12 75,33 60,47 41,39",
    ),
    (
        "gewerbering",
        "Gewerbering",
        91,
        78,
        88,
        72,
        86,
        95,
        84,
        55,
        72,
        90,
        72,
        44,
        "64,45 91,39 96,62 79,75 62,63",
    ),
    (
        "medienquartier",
        "Medienquartier",
        47,
        63,
        54,
        62,
        55,
        43,
        46,
        48,
        69,
        51,
        38,
        62,
        "31,61 60,61 62,82 35,91 17,76",
    ),
)

BUSINESS_TYPES: Final = {
    "gastronomy": {
        "price": 25_000,
        "revenue": 5_200,
        "cost": 3_400,
        "personnel": 2,
        "logistics": 1,
        "risk": 8,
    },
    "event_agency": {
        "price": 35_000,
        "revenue": 6_400,
        "cost": 4_200,
        "personnel": 2,
        "logistics": 1,
        "risk": 12,
    },
    "security_company": {
        "price": 60_000,
        "revenue": 9_000,
        "cost": 6_300,
        "personnel": 3,
        "logistics": 2,
        "risk": 16,
    },
    "logistics_company": {
        "price": 90_000,
        "revenue": 13_000,
        "cost": 8_500,
        "personnel": 4,
        "logistics": 3,
        "risk": 20,
    },
    "technology_company": {
        "price": 120_000,
        "revenue": 17_000,
        "cost": 11_500,
        "personnel": 5,
        "logistics": 2,
        "risk": 18,
    },
}

COMPANY_INDUSTRIES: Final[dict[str, CompanyIndustryDefinition]] = {
    "gastronomy": {
        "enterprise_value_cents": 20_000_000,
        "revenue_cents": 3_500_000,
        "cost_cents": 2_700_000,
        "employees": 6,
        "capacity": 2_500,
        "quality": 5_500,
        "market_share_bps": 120,
        "reputation_bps": 5_000,
        "compliance_bps": 6_500,
        "innovation_bps": 3_500,
        "risk_bps": 1_200,
    },
    "logistics": {
        "enterprise_value_cents": 20_000_000,
        "revenue_cents": 3_500_000,
        "cost_cents": 2_700_000,
        "employees": 8,
        "capacity": 3_000,
        "quality": 5_000,
        "market_share_bps": 120,
        "reputation_bps": 4_800,
        "compliance_bps": 6_000,
        "innovation_bps": 4_200,
        "risk_bps": 1_800,
    },
    "technology": {
        "enterprise_value_cents": 20_000_000,
        "revenue_cents": 3_500_000,
        "cost_cents": 2_700_000,
        "employees": 5,
        "capacity": 2_200,
        "quality": 5_200,
        "market_share_bps": 120,
        "reputation_bps": 5_200,
        "compliance_bps": 6_200,
        "innovation_bps": 6_000,
        "risk_bps": 1_600,
    },
}

COMPANY_INVESTMENTS: Final[dict[str, CompanyInvestmentDefinition]] = {
    "capacity": {"cost_cents": 500_000, "metric": "capacity", "increase": 500},
    "quality": {"cost_cents": 750_000, "metric": "quality", "increase": 400},
    "innovation": {
        "cost_cents": 1_000_000,
        "metric": "innovation_bps",
        "increase": 600,
    },
    "compliance": {
        "cost_cents": 800_000,
        "metric": "compliance_bps",
        "increase": 500,
    },
}

ECONOMY_MARKETS: Final[dict[str, EconomyMarketDefinition]] = {
    "gastronomy": {
        "demand_units": 10_000,
        "unit_revenue_cents": 1_400,
        "variable_cost_per_unit_cents": 680,
        "fixed_cost_cents": 1_000_000,
    },
    "logistics": {
        "demand_units": 10_000,
        "unit_revenue_cents": 1_167,
        "variable_cost_per_unit_cents": 600,
        "fixed_cost_cents": 900_000,
    },
    "technology": {
        "demand_units": 10_000,
        "unit_revenue_cents": 1_591,
        "variable_cost_per_unit_cents": 800,
        "fixed_cost_cents": 940_000,
    },
}

FACILITY_TYPES: Final = {
    "headquarters": {"cash": 0, "capital": 0, "hours": 0, "max_level": 5},
    "finance_office": {"cash": 20_000, "capital": 10_000, "hours": 2, "max_level": 5},
    "intelligence_center": {"cash": 25_000, "capital": 8_000, "hours": 3, "max_level": 5},
    "logistics_center": {"cash": 30_000, "capital": 15_000, "hours": 4, "max_level": 5},
    "personnel_academy": {"cash": 22_000, "capital": 12_000, "hours": 3, "max_level": 5},
    "compliance_office": {"cash": 35_000, "capital": 20_000, "hours": 6, "max_level": 5},
}

SPECIALIST_DEFINITIONS: Final[dict[str, SpecialistRoleDefinition]] = {
    "finance_director": {
        "base_salary_cents": 160_000,
        "primary_skill": "finance",
        "effect": "cost_reduction_bps",
    },
    "technology_expert": {
        "base_salary_cents": 180_000,
        "primary_skill": "technology",
        "effect": "attractiveness_bonus_points",
    },
    "market_analyst": {
        "base_salary_cents": 150_000,
        "primary_skill": "analysis",
        "effect": "revenue_bonus_bps",
    },
    "compliance_officer": {
        "base_salary_cents": 165_000,
        "primary_skill": "compliance",
        "effect": "attractiveness_bonus_points",
    },
    "logistics_expert": {
        "base_salary_cents": 170_000,
        "primary_skill": "logistics",
        "effect": "capacity_bonus_units",
    },
    "diplomat": {
        "base_salary_cents": 155_000,
        "primary_skill": "diplomacy",
        "effect": "attractiveness_bonus_points",
    },
}
SPECIALIST_ROLES: Final = tuple(SPECIALIST_DEFINITIONS)
AI_STRATEGIES: Final = (
    "growth",
    "efficiency",
    "innovation",
    "market_share",
    "stability",
)

OPERATION_TYPES: Final = {
    "business_expansion": {"minutes": 20, "difficulty": 30, "influence": 2, "pressure": 1},
    "intelligence_gathering": {"minutes": 15, "difficulty": 35, "intelligence": 5, "pressure": 2},
    "influence_project": {"minutes": 30, "difficulty": 42, "influence": 5, "pressure": 2},
    "diplomatic_mission": {"minutes": 25, "difficulty": 40, "influence": 3, "pressure": 1},
    "covert_market_project": {"minutes": 35, "difficulty": 58, "cash": 15_000, "pressure": 8},
}

RISK_POSTURES: Final = {
    "cautious": {"chance": 8, "duration": 1.35, "reward": 0.75, "risk": 0.6},
    "balanced": {"chance": 0, "duration": 1.0, "reward": 1.0, "risk": 1.0},
    "aggressive": {"chance": -5, "duration": 0.7, "reward": 1.35, "risk": 1.6},
}

PVP_OPERATION_TYPES: Final = {
    "intelligence_probe": {
        "minutes": 10,
        "cash": 2_500,
        "influence": 1,
        "base_power": 24,
        "effect_cap": 2,
    },
    "market_pressure": {
        "minutes": 20,
        "cash": 5_000,
        "influence": 2,
        "base_power": 30,
        "effect_cap": 3,
    },
    "influence_campaign": {
        "minutes": 30,
        "cash": 7_500,
        "influence": 3,
        "base_power": 36,
        "effect_cap": 5,
    },
    "abstract_disruption": {
        "minutes": 40,
        "cash": 10_000,
        "influence": 3,
        "base_power": 40,
        "effect_cap": 4,
    },
    "strategic_confrontation": {
        "minutes": 60,
        "cash": 15_000,
        "influence": 5,
        "base_power": 44,
        "effect_cap": 5,
    },
}

PVP_DEFENSE_ACTIONS: Final = {
    "observe": 6,
    "assign_security": 14,
    "reassign_specialists": 12,
    "request_cartel_support": 10,
    "reduce_business_activity": 16,
    "secure_information": 14,
    "attempt_mediation": 9,
    "prepare_counteroperation": 11,
}

TERRITORY_CONTROL_POINTS: Final = (
    "economic_network",
    "information_center",
    "logistics_node",
    "social_access",
    "digital_node",
    "coordination_center",
)

WAR_SCORE_WEIGHTS: Final = {
    "territorial": Decimal("0.25"),
    "economic": Decimal("0.20"),
    "operations": Decimal("0.20"),
    "intelligence": Decimal("0.15"),
    "participation": Decimal("0.10"),
    "stability": Decimal("0.10"),
}

RESEARCH: Final[dict[str, ResearchDefinition]] = {
    "distributed_command": {
        "category": "organization",
        "cash": 12_000,
        "capital": 4_000,
        "minutes": 60,
    },
    "market_analytics": {"category": "economy", "cash": 8_000, "capital": 8_000, "minutes": 75},
    "source_validation": {
        "category": "information",
        "cash": 10_000,
        "capital": 5_000,
        "minutes": 60,
    },
    "risk_early_warning": {"category": "security", "cash": 14_000, "capital": 6_000, "minutes": 90},
    "mediation_protocols": {
        "category": "diplomacy",
        "cash": 9_000,
        "capital": 4_000,
        "minutes": 60,
    },
    "predictive_systems": {
        "category": "technology",
        "cash": 16_000,
        "capital": 12_000,
        "minutes": 120,
    },
}

WORLD_EVENT_TEMPLATES_V1: Final[dict[str, WorldEventTemplateDefinition]] = {
    "port_strike": {
        "title": "Port strike",
        "description": "A fictional labor dispute constrains logistics capacity and city demand.",
        "default_scope_type": "city",
        "default_duration_minutes": 720,
        "effects": {
            "revenue_multiplier_bps": 8_500,
            "cost_multiplier_bps": 11_500,
            "demand_multiplier_bps": 8_000,
            "contract_probability_delta_bps": -1_000,
        },
    },
    "technology_boom": {
        "title": "Technology boom",
        "description": "Investment and specialist demand accelerate in the technology sector.",
        "default_scope_type": "industry",
        "default_duration_minutes": 1_440,
        "effects": {
            "revenue_multiplier_bps": 11_500,
            "demand_multiplier_bps": 11_800,
            "specialist_salary_multiplier_bps": 10_500,
            "stock_risk_delta_bps": 500,
        },
    },
    "real_estate_crisis": {
        "title": "Real-estate crisis",
        "description": "A fictional property correction changes costs and confidence.",
        "default_scope_type": "city",
        "default_duration_minutes": 1_440,
        "effects": {
            "cost_multiplier_bps": 10_800,
            "real_estate_cost_multiplier_bps": 7_000,
            "reputation_delta_bps": -500,
            "contract_probability_delta_bps": -700,
        },
    },
    "data_leak": {
        "title": "Data leak",
        "description": "An abstract information incident raises uncertainty and scrutiny.",
        "default_scope_type": "world",
        "default_duration_minutes": 480,
        "effects": {
            "reputation_delta_bps": -800,
            "investigation_pressure_delta": 12,
            "stock_risk_delta_bps": 1_500,
        },
    },
    "financial_audit": {
        "title": "Financial audit",
        "description": "A fictional compliance review temporarily increases operating pressure.",
        "default_scope_type": "company",
        "default_duration_minutes": 720,
        "effects": {
            "cost_multiplier_bps": 10_800,
            "reputation_delta_bps": -300,
            "investigation_pressure_delta": 10,
            "contract_probability_delta_bps": -1_000,
        },
    },
}

SEASON_SCORING_CATEGORIES: Final[tuple[str, ...]] = (
    "wealthiest_player",
    "portfolio_value",
    "entrepreneur",
    "largest_company",
    "strongest_cartel",
    "largest_public_company",
    "dividend_yield",
    "district_control",
    "diplomacy",
    "information_network",
    "stability",
    "crisis_recovery",
)

SEASON_TEMPLATE_V1: Final[SeasonTemplateDefinition] = {
    "name": "Cologne founding season",
    "phase_weights_bps": {
        "setup": 500,
        "early": 2_500,
        "mid": 3_500,
        "late": 2_500,
        "scoring": 1_000,
    },
    "goals": [
        {
            "key": "build_company",
            "title": "Build a sustainable company",
            "target": 1,
        },
        {
            "key": "form_cartel",
            "title": "Coordinate a cartel",
            "target": 1,
        },
        {
            "key": "reach_exchange",
            "title": "Bring a company to the exchange",
            "target": 1,
        },
    ],
    "scoring_categories": SEASON_SCORING_CATEGORIES,
}

WORLD_EVENTS: Final = {
    "port_strike": {"logistics": -20, "economic_activity": -5},
    "financial_audit": {"compliance_risk": 15, "revenue": -5},
    "data_leak": {"intel_visibility": 20, "trust": -5},
    "economic_crisis": {"revenue": -15, "employment": -8},
    "media_campaign": {"media_attention": 18, "legitimacy": -4},
    "technology_boom": {"digital_infrastructure": 12, "research_speed": 10},
    "major_raid": {"authority_presence": 20, "investigation_pressure": 12},
    "labor_shortage": {"employment": 8, "operating_cost": 12},
    "property_boom": {"property_value": 14, "operating_cost": 5},
    "security_crisis": {"safety": -15, "authority_presence": 10},
    "peace_initiative": {"treaty_cost": -20, "social_stability": 8},
    "supply_disruption": {"logistics": -12, "operating_cost": 9},
}

ROLE_PERMISSIONS: Final = {
    "leader": {"*"},
    "director": {"*"},
    "deputy": {
        "organization.view",
        "organization.edit_profile",
        "organization.invite",
        "organization.remove_members",
        "treasury.view",
        "operations.view",
        "operations.create",
        "intel.view_shared",
        "intel.share",
        "diplomacy.view",
        "diplomacy.propose",
        "diplomacy.accept",
        "research.view",
        "research.start",
        "audit.view",
        "wars.view",
        "wars.propose",
        "wars.declare",
        "wars.prepare",
        "wars.assign_members",
        "wars.commit_resources",
        "wars.negotiate_ceasefire",
        "wars.view_reports",
        "territory.view",
        "territory.claim",
        "territory.defend",
        "pvp.view_reports",
        "pvp.launch",
        "pvp.support",
        "pvp.defend",
        "alliances.view",
        "alliances.propose",
        "alliances.accept",
        "alliances.terminate",
    },
    "finance_lead": {
        "organization.view",
        "treasury.view",
        "treasury.deposit",
        "treasury.withdraw",
        "treasury.invest",
        "audit.view",
        "wars.commit_resources",
        "territory.defend",
    },
    "diplomacy_lead": {
        "organization.view",
        "diplomacy.view",
        "diplomacy.propose",
        "diplomacy.accept",
        "diplomacy.terminate",
        "wars.negotiate_ceasefire",
        "alliances.view",
        "alliances.propose",
        "alliances.accept",
        "alliances.terminate",
    },
    "intelligence_lead": {
        "organization.view",
        "intel.view_shared",
        "intel.share",
        "operations.view",
        "pvp.view_reports",
        "pvp.support",
    },
    "district_lead": {
        "organization.view",
        "operations.view",
        "operations.create",
        "territory.view",
        "territory.claim",
        "territory.defend",
        "territory.abandon",
    },
    "war_lead": {
        "organization.view",
        "wars.view",
        "wars.propose",
        "wars.declare",
        "wars.prepare",
        "wars.assign_members",
        "wars.commit_resources",
        "wars.negotiate_ceasefire",
        "wars.surrender",
        "wars.view_reports",
        "pvp.view_reports",
        "pvp.launch",
        "pvp.support",
        "pvp.defend",
        "territory.view",
        "territory.defend",
    },
    "recruitment_lead": {
        "organization.view",
        "organization.invite",
        "organization.remove_members",
    },
    "member": {
        "organization.view",
        "treasury.view",
        "operations.view",
        "intel.view_shared",
        "diplomacy.view",
        "research.view",
        "wars.view",
        "wars.prepare",
        "wars.view_reports",
        "territory.view",
        "territory.defend",
        "pvp.view_reports",
        "pvp.support",
        "pvp.defend",
        "alliances.view",
    },
    "candidate": {"organization.view"},
    "diplomat": {
        "organization.view",
        "diplomacy.view",
        "diplomacy.propose",
        "diplomacy.accept",
        "diplomacy.terminate",
        "wars.negotiate_ceasefire",
        "alliances.view",
        "alliances.propose",
        "alliances.accept",
        "alliances.terminate",
    },
    "strategist": {
        "organization.view",
        "projects.create",
        "projects.view",
        "territory.view",
        "territory.claim",
        "territory.defend",
        "territory.abandon",
        "operations.view",
        "operations.create",
        "wars.view",
        "wars.prepare",
    },
    "intelligence_officer": {
        "organization.view",
        "projects.view",
        "intel.view_shared",
        "intel.share",
        "operations.view",
        "pvp.view_reports",
        "pvp.support",
    },
}

CARTEL_PROJECT_TEMPLATES: Final[dict[str, CartelProjectTemplate]] = {
    "logistics_hub": {
        "title": "Logistics hub",
        "cash_cents": 1_500_000,
        "influence": 40,
        "intelligence": 10,
        "duration_hours": 72,
        "influence_kind": "economic",
        "influence_reward": 70,
    },
    "technology_center": {
        "title": "Technology center",
        "cash_cents": 2_000_000,
        "influence": 30,
        "intelligence": 30,
        "duration_hours": 96,
        "influence_kind": "digital",
        "influence_reward": 80,
    },
    "media_campaign": {
        "title": "Media campaign",
        "cash_cents": 750_000,
        "influence": 60,
        "intelligence": 20,
        "duration_hours": 48,
        "influence_kind": "social",
        "influence_reward": 55,
    },
    "compliance_network": {
        "title": "Compliance network",
        "cash_cents": 1_250_000,
        "influence": 25,
        "intelligence": 50,
        "duration_hours": 72,
        "influence_kind": "society",
        "influence_reward": 60,
    },
    "trade_center": {
        "title": "Trade center",
        "cash_cents": 2_500_000,
        "influence": 70,
        "intelligence": 20,
        "duration_hours": 120,
        "influence_kind": "economic",
        "influence_reward": 100,
    },
}
