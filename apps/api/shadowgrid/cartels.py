from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.domain import (
    apply_profile_resource,
    audit,
    create_notification,
    get_idempotent,
    remember_idempotent,
    safe_commit,
)
from shadowgrid.errors import DomainError
from shadowgrid.finance import (
    cents_to_money,
    ensure_system_account,
    post_balanced_transfer,
    transfer_profile_cash_to_account,
)
from shadowgrid.game_config import ARCHETYPES, CARTEL_PROJECT_TEMPLATES, ROLE_PERMISSIONS
from shadowgrid.intelligence import effective_project_deadline
from shadowgrid.models import (
    Account,
    AuditLog,
    CartelDistrictInfluence,
    CartelExpense,
    CartelProject,
    CartelProjectContribution,
    District,
    IdempotencyRecord,
    LedgerTransaction,
    Organization,
    OrganizationInvite,
    OrganizationMembership,
    PlayerProfile,
    TerritoryControlPoint,
    User,
    World,
    as_utc,
)
from shadowgrid.realtime import emit_realtime_event

_cartel_mutation_lock = threading.RLock()
LEADER_ROLES = {"leader", "director"}
FINANCE_ROLES = {"leader", "director", "deputy", "finance_lead"}
PROJECT_MANAGER_ROLES = {
    "leader",
    "director",
    "deputy",
    "strategist",
    "district_lead",
}
ASSIGNABLE_ROLES = {
    "member",
    "finance_lead",
    "diplomat",
    "strategist",
    "intelligence_officer",
}
POINT_TYPE_BY_INFLUENCE_KIND = {
    "economic": "economic_network",
    "digital": "digital_node",
    "social": "social_access",
    "society": "social_access",
    "intelligence": "information_center",
    "logistics": "logistics_node",
}


def _lock_world(db: Session, world_id: str) -> World:
    world = db.scalar(select(World).where(World.id == world_id).with_for_update())
    if world is None:
        raise DomainError(404, "world.not_found", "World not found")
    return world


def _cartel(db: Session, cartel_id: str, world_id: str | None = None) -> Organization:
    cartel = db.get(Organization, cartel_id)
    if (
        cartel is None
        or cartel.status != "active"
        or (world_id is not None and cartel.world_id != world_id)
    ):
        raise DomainError(404, "cartel.not_found", "Active cartel not found")
    return cartel


def active_membership(
    db: Session,
    profile_id: str,
    cartel_id: str | None = None,
    *,
    lock: bool = False,
) -> OrganizationMembership:
    query = select(OrganizationMembership).where(
        OrganizationMembership.profile_id == profile_id,
        OrganizationMembership.status == "active",
    )
    if cartel_id is not None:
        query = query.where(OrganizationMembership.organization_id == cartel_id)
    if lock:
        query = query.with_for_update()
    membership = db.scalar(query)
    if membership is None:
        raise DomainError(403, "cartel.membership_required", "Active cartel membership required")
    return membership


def _require_role(
    db: Session,
    profile_id: str,
    cartel_id: str,
    roles: set[str],
    *,
    lock: bool = False,
) -> OrganizationMembership:
    membership = active_membership(db, profile_id, cartel_id, lock=lock)
    if membership.role not in roles:
        raise DomainError(403, "cartel.permission_denied", "Cartel role permission denied")
    return membership


def ensure_cartel_account(db: Session, cartel: Organization) -> Account:
    account = db.scalar(
        select(Account)
        .where(
            Account.world_id == cartel.world_id,
            Account.owner_type == "organization",
            Account.owner_id == cartel.id,
            Account.currency == "EUR",
        )
        .with_for_update()
    )
    if account is None:
        account = Account(
            world_id=cartel.world_id,
            owner_type="organization",
            owner_id=cartel.id,
            currency="EUR",
            balance_cents=0,
        )
        db.add(account)
        db.flush()
        opening_cents = int((Decimal(cartel.treasury_cash) * Decimal(100)).to_integral_value())
        if opening_cents > 0:
            post_balanced_transfer(
                db,
                world_id=cartel.world_id,
                source_account=ensure_system_account(db, cartel.world_id),
                target_account=account,
                amount_cents=opening_cents,
                transaction_type="cartel_legacy_opening_balance",
                idempotency_key=f"cartel-opening:{cartel.id}",
                reference_type="organization",
                reference_id=cartel.id,
                actor_profile_id=None,
            )
    return account


def create_cartel(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    name: str,
    tag: str,
    archetype: str,
    description: str,
    governance_model: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> Organization:
    with _cartel_mutation_lock:
        previous = get_idempotent(db, user.id, idempotency_key, "cartel.create")
        if previous is not None:
            existing = db.get(Organization, previous.resource_id)
            if existing is not None:
                return existing
        _lock_world(db, profile.world_id)
        if profile.tutorial_step < 3:
            raise DomainError(
                409,
                "cartel.progress_required",
                "Complete the cartel tutorial milestone first",
            )
        existing_membership = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.profile_id == profile.id,
                OrganizationMembership.status == "active",
            )
        )
        if existing_membership is not None:
            raise DomainError(409, "cartel.already_member", "Profile already belongs to a cartel")
        if archetype not in ARCHETYPES:
            raise DomainError(422, "cartel.invalid_archetype", "Unknown cartel archetype")
        normalized_name = " ".join(name.split())
        normalized_tag = tag.strip().upper()
        duplicate = db.scalar(
            select(Organization.id).where(
                Organization.world_id == profile.world_id,
                (func.lower(Organization.name) == normalized_name.lower())
                | (func.lower(Organization.tag) == normalized_tag.lower()),
            )
        )
        if duplicate is not None:
            raise DomainError(409, "cartel.name_taken", "Cartel name or tag is already in use")
        cartel = Organization(
            world_id=profile.world_id,
            city_id=profile.city_id,
            name=normalized_name,
            tag=normalized_tag,
            archetype=archetype,
            description=description.strip(),
            governance_model=governance_model,
            approval_threshold_cents=settings.cartel_default_approval_threshold_cents,
            single_spend_limit_cents=settings.cartel_default_single_spend_limit_cents,
        )
        db.add(cartel)
        db.flush()
        ensure_cartel_account(db, cartel)
        if settings.cartel_creation_cost_cents:
            apply_profile_resource(
                db,
                profile.id,
                "cash",
                -cents_to_money(settings.cartel_creation_cost_cents),
                reason="cartel_creation",
                reference_type="organization",
                reference_id=cartel.id,
                idempotency_key=f"cartel-create:{idempotency_key}",
            )
        db.add(
            OrganizationMembership(
                organization_id=cartel.id,
                profile_id=profile.id,
                role="leader",
                status="active",
            )
        )
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.create",
            cartel.id,
            {"cartel_id": cartel.id},
        )
        audit(
            db,
            user.id,
            "cartel.created",
            "organization",
            cartel.id,
            request_id,
            {"organization_id": cartel.id, "profile_id": profile.id},
        )
        safe_commit(db)
        return cartel


def create_invitation(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    email: str,
    idempotency_key: str,
    request_id: str,
) -> OrganizationInvite:
    with _cartel_mutation_lock:
        previous = get_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.invitation.create",
        )
        if previous is not None:
            invitation = db.get(OrganizationInvite, previous.resource_id)
            if invitation is not None:
                return invitation
        _require_role(
            db,
            profile.id,
            cartel_id,
            {"leader", "director", "deputy", "recruitment_lead"},
        )
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        member_count = db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == cartel.id,
                OrganizationMembership.status == "active",
            )
        )
        if int(member_count or 0) >= cartel.member_limit:
            raise DomainError(409, "cartel.member_limit", "Cartel member limit reached")
        normalized_email = email.strip().lower()
        target_user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
        if target_user is None:
            raise DomainError(404, "cartel.invitee_not_found", "Verified player not found")
        target_profile = db.scalar(
            select(PlayerProfile).where(
                PlayerProfile.user_id == target_user.id,
                PlayerProfile.world_id == cartel.world_id,
            )
        )
        if target_profile is None:
            raise DomainError(404, "cartel.invitee_not_found", "Player has not joined this world")
        already_member = db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.profile_id == target_profile.id,
                OrganizationMembership.status == "active",
            )
        )
        if already_member is not None:
            raise DomainError(409, "cartel.invitee_already_member", "Player already has a cartel")
        existing = db.scalar(
            select(OrganizationInvite).where(
                OrganizationInvite.organization_id == cartel.id,
                OrganizationInvite.email == normalized_email,
                OrganizationInvite.status == "pending",
            )
        )
        if existing is not None and as_utc(existing.expires_at) >= datetime.now(UTC):
            remember_idempotent(
                db,
                user.id,
                idempotency_key,
                "cartel.invitation.create",
                existing.id,
                {"invitation_id": existing.id},
            )
            safe_commit(db)
            return existing
        if existing is not None:
            existing.status = "expired"
        invitation = OrganizationInvite(
            organization_id=cartel.id,
            invited_by_profile_id=profile.id,
            email=normalized_email,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(days=3),
        )
        db.add(invitation)
        db.flush()
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.invitation.create",
            invitation.id,
            {"invitation_id": invitation.id},
        )
        audit(
            db,
            user.id,
            "cartel.invitation_created",
            "organization",
            cartel.id,
            request_id,
            {"organization_id": cartel.id, "invitation_id": invitation.id},
        )
        create_notification(
            db,
            target_user.id,
            "cartel.invitation.created",
            f"Invitation to {cartel.name}",
            "A cartel invitation is waiting for your response.",
            {
                "invitation_id": invitation.id,
                "cartel_id": cartel.id,
            },
        )
        emit_realtime_event(
            db,
            world_id=cartel.world_id,
            event_type="cartel.invitation.created",
            payload={
                "invitation_id": invitation.id,
                "cartel_id": cartel.id,
            },
            audience_type="player",
            audience_id=target_profile.id,
            dedupe_key=f"cartel-invitation:{invitation.id}",
        )
        safe_commit(db)
        return invitation


def list_invitations(db: Session, user: User, profile: PlayerProfile) -> list[OrganizationInvite]:
    now = datetime.now(UTC)
    invitations = list(
        db.scalars(
            select(OrganizationInvite)
            .join(Organization, Organization.id == OrganizationInvite.organization_id)
            .where(
                OrganizationInvite.email == user.email.lower(),
                OrganizationInvite.status == "pending",
                OrganizationInvite.expires_at >= now,
                Organization.world_id == profile.world_id,
                Organization.status == "active",
            )
            .order_by(OrganizationInvite.created_at.desc())
        )
    )
    return invitations


def join_cartel(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    invitation_id: str,
    idempotency_key: str,
    request_id: str,
) -> OrganizationMembership:
    with _cartel_mutation_lock:
        previous = get_idempotent(db, user.id, idempotency_key, "cartel.join")
        if previous is not None:
            membership = db.get(OrganizationMembership, previous.resource_id)
            if membership is not None:
                return membership
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        invitation = db.scalar(
            select(OrganizationInvite)
            .where(
                OrganizationInvite.id == invitation_id,
                OrganizationInvite.organization_id == cartel.id,
            )
            .with_for_update()
        )
        if (
            invitation is None
            or invitation.status != "pending"
            or invitation.email != user.email.lower()
            or as_utc(invitation.expires_at) < datetime.now(UTC)
        ):
            raise DomainError(404, "cartel.invitation_not_found", "Active invitation not found")
        existing = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.profile_id == profile.id,
                OrganizationMembership.status == "active",
            )
        )
        if existing is not None:
            raise DomainError(409, "cartel.already_member", "Profile already belongs to a cartel")
        member_count = db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == cartel.id,
                OrganizationMembership.status == "active",
            )
        )
        if int(member_count or 0) >= cartel.member_limit:
            raise DomainError(409, "cartel.member_limit", "Cartel member limit reached")
        prior = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == cartel.id,
                OrganizationMembership.profile_id == profile.id,
            )
        )
        if prior is None:
            membership = OrganizationMembership(
                organization_id=cartel.id,
                profile_id=profile.id,
                role="member",
                status="active",
            )
            db.add(membership)
        else:
            membership = prior
            membership.role = "member"
            membership.status = "active"
            membership.joined_at = datetime.now(UTC)
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(UTC)
        db.flush()
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.join",
            membership.id,
            {"membership_id": membership.id, "cartel_id": cartel.id},
        )
        audit(
            db,
            user.id,
            "cartel.member_joined",
            "organization",
            cartel.id,
            request_id,
            {"organization_id": cartel.id, "profile_id": profile.id},
        )
        safe_commit(db)
        return membership


def leave_cartel(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    idempotency_key: str,
    request_id: str,
) -> None:
    with _cartel_mutation_lock:
        if get_idempotent(db, user.id, idempotency_key, "cartel.leave") is not None:
            return
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        membership = active_membership(db, profile.id, cartel.id, lock=True)
        if membership.role in LEADER_ROLES:
            raise DomainError(
                409,
                "cartel.leader_transfer_required",
                "Transfer leadership before leaving the cartel",
            )
        membership.status = "left"
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.leave",
            membership.id,
            {"membership_id": membership.id, "cartel_id": cartel.id},
        )
        audit(
            db,
            user.id,
            "cartel.member_left",
            "organization",
            cartel.id,
            request_id,
            {"organization_id": cartel.id, "profile_id": profile.id},
        )
        safe_commit(db)


def update_member_role(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    target_profile_id: str,
    role: str,
    idempotency_key: str,
    request_id: str,
) -> OrganizationMembership:
    if role not in ASSIGNABLE_ROLES:
        raise DomainError(422, "cartel.invalid_role", "Unsupported cartel role")
    with _cartel_mutation_lock:
        previous = get_idempotent(db, user.id, idempotency_key, "cartel.role.update")
        if previous is not None:
            membership = db.get(OrganizationMembership, previous.resource_id)
            if membership is not None:
                return membership
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        _require_role(db, profile.id, cartel.id, LEADER_ROLES, lock=True)
        target = db.scalar(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == cartel.id,
                OrganizationMembership.profile_id == target_profile_id,
                OrganizationMembership.status == "active",
            )
            .with_for_update()
        )
        if target is None:
            raise DomainError(404, "cartel.member_not_found", "Active member not found")
        if target.role in LEADER_ROLES:
            raise DomainError(
                409,
                "cartel.leader_protected",
                "Use the leadership transfer workflow",
            )
        previous_role = target.role
        target.role = role
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.role.update",
            target.id,
            {"membership_id": target.id, "role": role},
        )
        audit(
            db,
            user.id,
            "cartel.role_changed",
            "organization",
            cartel.id,
            request_id,
            {
                "organization_id": cartel.id,
                "target_profile_id": target_profile_id,
                "previous_role": previous_role,
                "new_role": role,
            },
        )
        safe_commit(db)
        return target


def transfer_leadership(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    target_profile_id: str,
    idempotency_key: str,
    request_id: str,
) -> tuple[OrganizationMembership, OrganizationMembership]:
    with _cartel_mutation_lock:
        previous = get_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.leadership.transfer",
        )
        if previous is not None:
            target = db.get(OrganizationMembership, previous.resource_id)
            current = db.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.profile_id == profile.id,
                    OrganizationMembership.organization_id == cartel_id,
                )
            )
            if target is not None and current is not None:
                return current, target
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        rows = list(
            db.scalars(
                select(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == cartel.id,
                    OrganizationMembership.profile_id.in_([profile.id, target_profile_id]),
                    OrganizationMembership.status == "active",
                )
                .order_by(OrganizationMembership.profile_id)
                .with_for_update()
            )
        )
        current = next((item for item in rows if item.profile_id == profile.id), None)
        target = next((item for item in rows if item.profile_id == target_profile_id), None)
        if current is None or current.role not in LEADER_ROLES:
            raise DomainError(
                403, "cartel.permission_denied", "Only the cartel leader may transfer"
            )
        if target is None or target.profile_id == current.profile_id:
            raise DomainError(404, "cartel.member_not_found", "Target member not found")
        current.role = "member"
        target.role = "leader"
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.leadership.transfer",
            target.id,
            {"new_leader_membership_id": target.id, "cartel_id": cartel.id},
        )
        audit(
            db,
            user.id,
            "cartel.leadership_transferred",
            "organization",
            cartel.id,
            request_id,
            {
                "organization_id": cartel.id,
                "previous_leader_profile_id": current.profile_id,
                "new_leader_profile_id": target.profile_id,
            },
        )
        safe_commit(db)
        return current, target


def deposit_treasury(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    amount_cents: int,
    idempotency_key: str,
    request_id: str,
) -> Account:
    with _cartel_mutation_lock:
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        active_membership(db, profile.id, cartel.id)
        account = ensure_cartel_account(db, cartel)
        transaction_key = f"cartel-deposit:{cartel.id}:{idempotency_key}"
        existing = db.scalar(
            select(LedgerTransaction).where(
                LedgerTransaction.world_id == cartel.world_id,
                LedgerTransaction.idempotency_key == transaction_key,
            )
        )
        if existing is None:
            transfer_profile_cash_to_account(
                db,
                profile,
                account,
                amount_cents=amount_cents,
                transaction_type="cartel_treasury_deposit",
                idempotency_key=transaction_key,
                reference_type="organization",
                reference_id=cartel.id,
            )
            cartel.treasury_cash = cents_to_money(account.balance_cents)
            audit(
                db,
                user.id,
                "cartel.treasury_deposited",
                "organization",
                cartel.id,
                request_id,
                {
                    "organization_id": cartel.id,
                    "amount_cents": amount_cents,
                },
            )
            safe_commit(db)
        return account


def _execute_expense(
    db: Session,
    *,
    cartel: Organization,
    account: Account,
    expense: CartelExpense,
    actor_profile_id: str,
) -> None:
    transaction = post_balanced_transfer(
        db,
        world_id=cartel.world_id,
        source_account=account,
        target_account=ensure_system_account(db, cartel.world_id),
        amount_cents=expense.amount_cents,
        transaction_type="cartel_treasury_expense",
        idempotency_key=f"cartel-expense:{expense.id}",
        reference_type="cartel_expense",
        reference_id=expense.id,
        actor_profile_id=actor_profile_id,
        metadata={"organization_id": cartel.id, "purpose": expense.purpose},
    )
    expense.transaction_id = transaction.id
    expense.status = "approved"
    expense.resolved_at = datetime.now(UTC)
    cartel.treasury_cash = cents_to_money(account.balance_cents)


def request_expense(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    amount_cents: int,
    purpose: str,
    idempotency_key: str,
    request_id: str,
) -> CartelExpense:
    with _cartel_mutation_lock:
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        _require_role(db, profile.id, cartel.id, FINANCE_ROLES)
        if amount_cents > cartel.single_spend_limit_cents:
            raise DomainError(
                422,
                "cartel.expense_limit",
                "Expense exceeds the configured single-spend limit",
            )
        existing = db.scalar(
            select(CartelExpense).where(
                CartelExpense.organization_id == cartel.id,
                CartelExpense.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        requires_approval = amount_cents > cartel.approval_threshold_cents
        expense = CartelExpense(
            organization_id=cartel.id,
            requested_by_profile_id=profile.id,
            amount_cents=amount_cents,
            purpose=purpose.strip(),
            requires_approval=requires_approval,
            status="pending",
            idempotency_key=idempotency_key,
        )
        db.add(expense)
        db.flush()
        account = ensure_cartel_account(db, cartel)
        if not requires_approval:
            expense.approved_by_profile_id = profile.id
            _execute_expense(
                db,
                cartel=cartel,
                account=account,
                expense=expense,
                actor_profile_id=profile.id,
            )
        audit(
            db,
            user.id,
            "cartel.expense_requested",
            "organization",
            cartel.id,
            request_id,
            {
                "organization_id": cartel.id,
                "expense_id": expense.id,
                "amount_cents": amount_cents,
                "requires_approval": requires_approval,
            },
        )
        safe_commit(db)
        return expense


def approve_expense(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    expense_id: str,
    request_id: str,
) -> CartelExpense:
    with _cartel_mutation_lock:
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        _require_role(db, profile.id, cartel.id, FINANCE_ROLES)
        expense = db.scalar(
            select(CartelExpense)
            .where(
                CartelExpense.id == expense_id,
                CartelExpense.organization_id == cartel.id,
            )
            .with_for_update()
        )
        if expense is None:
            raise DomainError(404, "cartel.expense_not_found", "Expense request not found")
        if expense.status == "approved":
            return expense
        if expense.status != "pending":
            raise DomainError(409, "cartel.expense_resolved", "Expense request is already resolved")
        if expense.requested_by_profile_id == profile.id:
            raise DomainError(
                409,
                "cartel.expense_self_approval",
                "Approval-required expenses need a different approver",
            )
        expense.approved_by_profile_id = profile.id
        _execute_expense(
            db,
            cartel=cartel,
            account=ensure_cartel_account(db, cartel),
            expense=expense,
            actor_profile_id=profile.id,
        )
        audit(
            db,
            user.id,
            "cartel.expense_approved",
            "organization",
            cartel.id,
            request_id,
            {
                "organization_id": cartel.id,
                "expense_id": expense.id,
                "amount_cents": expense.amount_cents,
            },
        )
        safe_commit(db)
        return expense


def create_project(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    district_id: str,
    project_type: str,
    idempotency_key: str,
    request_id: str,
) -> CartelProject:
    template = CARTEL_PROJECT_TEMPLATES.get(project_type)
    if template is None:
        raise DomainError(422, "cartel.project_type_invalid", "Unknown cartel project type")
    with _cartel_mutation_lock:
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        _require_role(db, profile.id, cartel.id, PROJECT_MANAGER_ROLES)
        existing = db.scalar(
            select(CartelProject).where(
                CartelProject.organization_id == cartel.id,
                CartelProject.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        district = db.get(District, district_id)
        if district is None or district.world_id != cartel.world_id:
            raise DomainError(404, "district.not_found", "District not found in this world")
        now = datetime.now(UTC)
        project = CartelProject(
            world_id=cartel.world_id,
            organization_id=cartel.id,
            district_id=district.id,
            project_type=project_type,
            title=template["title"],
            required_cash_cents=template["cash_cents"],
            required_influence=template["influence"],
            required_intelligence=template["intelligence"],
            influence_kind=template["influence_kind"],
            influence_reward=template["influence_reward"],
            idempotency_key=idempotency_key,
            created_by_profile_id=profile.id,
            starts_at=now,
            ends_at=now + timedelta(hours=template["duration_hours"]),
        )
        db.add(project)
        db.flush()
        audit(
            db,
            user.id,
            "cartel.project_created",
            "organization",
            cartel.id,
            request_id,
            {
                "organization_id": cartel.id,
                "project_id": project.id,
                "project_type": project.project_type,
                "district_id": project.district_id,
            },
        )
        emit_realtime_event(
            db,
            world_id=cartel.world_id,
            event_type="cartel.project.updated",
            payload={
                "project_id": project.id,
                "cartel_id": cartel.id,
                "status": project.status,
            },
            audience_type="cartel",
            audience_id=cartel.id,
            dedupe_key=f"cartel-project-created:{project.id}",
        )
        safe_commit(db)
        return project


def _project_requirement(project: CartelProject, resource_type: str) -> tuple[str, int]:
    fields = {
        "cash": ("contributed_cash_cents", project.required_cash_cents),
        "influence": ("contributed_influence", project.required_influence),
        "intelligence": ("contributed_intelligence", project.required_intelligence),
    }
    try:
        return fields[resource_type]
    except KeyError as exc:
        raise DomainError(
            422,
            "cartel.project_resource_invalid",
            "Unsupported project contribution resource",
        ) from exc


def _control_for_scores(
    scores: list[tuple[str, int]],
    settings: Settings,
) -> tuple[str | None, str, int]:
    ordered = sorted(scores, key=lambda item: (-item[1], item[0]))
    if not ordered:
        return None, "neutral", 0
    top_id, top_points = ordered[0]
    runner_up = ordered[1][1] if len(ordered) > 1 else 0
    if top_points < settings.cartel_control_threshold:
        return None, "neutral", top_points
    if top_points - runner_up < settings.cartel_control_margin:
        return None, "contested", top_points
    return top_id, "controlled", top_points


def _recalculate_control_point(
    db: Session,
    project: CartelProject,
    settings: Settings,
) -> None:
    point_type = POINT_TYPE_BY_INFLUENCE_KIND.get(project.influence_kind, "coordination_center")
    rows = list(
        db.execute(
            select(
                CartelDistrictInfluence.organization_id,
                CartelDistrictInfluence.points,
            ).where(
                CartelDistrictInfluence.district_id == project.district_id,
                CartelDistrictInfluence.kind == project.influence_kind,
            )
        )
    )
    controller, status, top_points = _control_for_scores(
        [(str(cartel_id), int(points)) for cartel_id, points in rows],
        settings,
    )
    point = db.scalar(
        select(TerritoryControlPoint)
        .where(
            TerritoryControlPoint.district_id == project.district_id,
            TerritoryControlPoint.point_type == point_type,
        )
        .with_for_update()
    )
    if point is not None:
        point.controlling_cartel_id = controller
        point.status = status
        point.control_value = Decimal(top_points)
        point.version += 1


def contribute_to_project(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    project_id: str,
    resource_type: str,
    amount_units: int,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> CartelProject:
    with _cartel_mutation_lock:
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        active_membership(db, profile.id, cartel.id)
        existing = db.scalar(
            select(CartelProjectContribution).where(
                CartelProjectContribution.profile_id == profile.id,
                CartelProjectContribution.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            project = db.get(CartelProject, existing.project_id)
            if project is None:
                raise DomainError(409, "cartel.project_missing", "Project no longer exists")
            return project
        project = db.scalar(
            select(CartelProject)
            .where(
                CartelProject.id == project_id,
                CartelProject.organization_id == cartel.id,
            )
            .with_for_update()
        )
        if project is None:
            raise DomainError(404, "cartel.project_not_found", "Cartel project not found")
        if project.status != "active":
            raise DomainError(409, "cartel.project_closed", "Cartel project is not active")
        if effective_project_deadline(db, project) < datetime.now(UTC):
            raise DomainError(
                409, "cartel.project_expired", "Cartel project contribution window ended"
            )
        field, required = _project_requirement(project, resource_type)
        current = int(getattr(project, field))
        if current + amount_units > required:
            raise DomainError(
                422,
                "cartel.project_excess_contribution",
                "Contribution exceeds the remaining project requirement",
            )
        transaction_id: str | None = None
        if resource_type == "cash":
            transaction = transfer_profile_cash_to_account(
                db,
                profile,
                ensure_system_account(db, cartel.world_id),
                amount_cents=amount_units,
                transaction_type="cartel_project_contribution",
                idempotency_key=f"cartel-project:{profile.id}:{idempotency_key}",
                reference_type="cartel_project",
                reference_id=project.id,
            )
            transaction_id = transaction.id
        else:
            apply_profile_resource(
                db,
                profile.id,
                resource_type,
                -amount_units,
                reason="cartel_project_contribution",
                reference_type="cartel_project",
                reference_id=project.id,
                idempotency_key=f"cartel-project:{idempotency_key}",
            )
        setattr(project, field, current + amount_units)
        contribution = CartelProjectContribution(
            project_id=project.id,
            organization_id=cartel.id,
            profile_id=profile.id,
            resource_type=resource_type,
            amount_units=amount_units,
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
        )
        db.add(contribution)
        if (
            project.contributed_cash_cents >= project.required_cash_cents
            and project.contributed_influence >= project.required_influence
            and project.contributed_intelligence >= project.required_intelligence
        ):
            influence = db.scalar(
                select(CartelDistrictInfluence)
                .where(
                    CartelDistrictInfluence.organization_id == cartel.id,
                    CartelDistrictInfluence.district_id == project.district_id,
                    CartelDistrictInfluence.kind == project.influence_kind,
                )
                .with_for_update()
            )
            if influence is None:
                influence = CartelDistrictInfluence(
                    world_id=cartel.world_id,
                    organization_id=cartel.id,
                    district_id=project.district_id,
                    kind=project.influence_kind,
                    points=0,
                )
                db.add(influence)
                db.flush()
            influence.points += project.influence_reward
            influence.version += 1
            project.status = "completed"
            project.completed_at = datetime.now(UTC)
            db.flush()
            _recalculate_control_point(db, project, settings)
        audit(
            db,
            user.id,
            "cartel.project_contributed",
            "organization",
            cartel.id,
            request_id,
            {
                "organization_id": cartel.id,
                "project_id": project.id,
                "resource_type": resource_type,
                "amount_units": amount_units,
                "completed": project.status == "completed",
            },
        )
        db.flush()
        emit_realtime_event(
            db,
            world_id=cartel.world_id,
            event_type="cartel.project.updated",
            payload={
                "project_id": project.id,
                "cartel_id": cartel.id,
                "status": project.status,
            },
            audience_type="cartel",
            audience_id=cartel.id,
            dedupe_key=f"cartel-project-contribution:{contribution.id}",
        )
        safe_commit(db)
        return project


def district_influence(
    db: Session,
    *,
    world_id: str,
    city_id: str,
    settings: Settings,
) -> list[dict[str, Any]]:
    districts = list(
        db.scalars(
            select(District)
            .where(District.world_id == world_id, District.city_id == city_id)
            .order_by(District.name)
        )
    )
    result: list[dict[str, Any]] = []
    for district in districts:
        rows = list(
            db.execute(
                select(
                    CartelDistrictInfluence.organization_id,
                    Organization.name,
                    CartelDistrictInfluence.kind,
                    CartelDistrictInfluence.points,
                )
                .join(
                    Organization,
                    Organization.id == CartelDistrictInfluence.organization_id,
                )
                .where(CartelDistrictInfluence.district_id == district.id)
                .order_by(CartelDistrictInfluence.points.desc(), Organization.name)
            )
        )
        totals: dict[str, int] = {}
        names: dict[str, str] = {}
        entries: list[dict[str, Any]] = []
        for organization_id, name, kind, points in rows:
            key = str(organization_id)
            totals[key] = totals.get(key, 0) + int(points)
            names[key] = str(name)
            entries.append(
                {
                    "cartel_id": key,
                    "cartel_name": str(name),
                    "kind": str(kind),
                    "points": int(points),
                }
            )
        controller, status, top_points = _control_for_scores(list(totals.items()), settings)
        result.append(
            {
                "district_id": district.id,
                "district_name": district.name,
                "status": status,
                "controlling_cartel_id": controller,
                "controlling_cartel_name": names.get(controller) if controller else None,
                "top_points": top_points,
                "entries": entries,
            }
        )
    return result


def cartel_rankings(db: Session, world_id: str) -> list[dict[str, Any]]:
    world = db.get(World, world_id)
    if world is None:
        raise DomainError(404, "world.not_found", "World not found")
    cartels = list(
        db.scalars(
            select(Organization)
            .where(Organization.world_id == world_id, Organization.status == "active")
            .order_by(Organization.name)
        )
    )
    rankings: list[dict[str, Any]] = []
    for cartel in cartels:
        account = db.scalar(
            select(Account).where(
                Account.world_id == world_id,
                Account.owner_type == "organization",
                Account.owner_id == cartel.id,
            )
        )
        member_count = int(
            db.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == cartel.id,
                    OrganizationMembership.status == "active",
                )
            )
            or 0
        )
        project_count = int(
            db.scalar(
                select(func.count())
                .select_from(CartelProject)
                .where(
                    CartelProject.organization_id == cartel.id,
                    CartelProject.status == "completed",
                )
            )
            or 0
        )
        influence = int(
            db.scalar(
                select(func.coalesce(func.sum(CartelDistrictInfluence.points), 0)).where(
                    CartelDistrictInfluence.organization_id == cartel.id
                )
            )
            or 0
        )
        treasury_cents = account.balance_cents if account is not None else 0
        score = treasury_cents // 10_000 + member_count * 100 + project_count * 250 + influence * 10
        rankings.append(
            {
                "cartel_id": cartel.id,
                "name": cartel.name,
                "tag": cartel.tag,
                "season_number": world.season_number,
                "score": score,
                "treasury_cents": treasury_cents,
                "member_count": member_count,
                "completed_projects": project_count,
                "influence": influence,
            }
        )
    rankings.sort(key=lambda item: (-int(item["score"]), str(item["name"])))
    for rank, item in enumerate(rankings, start=1):
        item["rank"] = rank
    return rankings


def dissolve_cartel(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    cartel_id: str,
    idempotency_key: str,
    request_id: str,
) -> None:
    with _cartel_mutation_lock:
        if get_idempotent(db, user.id, idempotency_key, "cartel.dissolve") is not None:
            return
        cartel = _cartel(db, cartel_id, profile.world_id)
        _lock_world(db, cartel.world_id)
        leader = _require_role(db, profile.id, cartel.id, LEADER_ROLES, lock=True)
        account = ensure_cartel_account(db, cartel)
        members = int(
            db.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == cartel.id,
                    OrganizationMembership.status == "active",
                )
            )
            or 0
        )
        active_projects = db.scalar(
            select(CartelProject.id).where(
                CartelProject.organization_id == cartel.id,
                CartelProject.status == "active",
            )
        )
        pending_expense = db.scalar(
            select(CartelExpense.id).where(
                CartelExpense.organization_id == cartel.id,
                CartelExpense.status == "pending",
            )
        )
        if members != 1 or account.balance_cents != 0 or active_projects or pending_expense:
            raise DomainError(
                409,
                "cartel.dissolution_protected",
                "Dissolution requires one member, an empty treasury and no active obligations",
            )
        cartel.status = "dissolved"
        cartel.dissolved_at = datetime.now(UTC)
        leader.status = "left"
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "cartel.dissolve",
            cartel.id,
            {"cartel_id": cartel.id},
        )
        audit(
            db,
            user.id,
            "cartel.dissolved",
            "organization",
            cartel.id,
            request_id,
            {"organization_id": cartel.id},
        )
        safe_commit(db)


def cartel_activity(db: Session, cartel_id: str, profile_id: str) -> list[AuditLog]:
    active_membership(db, profile_id, cartel_id)
    return list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.target_type == "organization",
                AuditLog.target_id == cartel_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(100)
        )
    )


def cartel_permissions(role: str | None) -> list[str]:
    if role is None:
        return []
    permissions = ROLE_PERMISSIONS.get(role, set())
    return sorted(permissions)


def cartel_idempotency_record(
    db: Session,
    user_id: str,
    key: str,
    scope: str,
) -> IdempotencyRecord | None:
    return get_idempotent(db, user_id, key, scope)
