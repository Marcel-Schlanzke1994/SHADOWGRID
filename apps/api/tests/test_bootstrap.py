from pydantic import SecretStr
from shadowgrid.bootstrap import bootstrap_admin, bootstrap_world
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.game_config import START_CITY, WORLD_SLUG
from shadowgrid.models import City, District, User, World, WorldEvent
from sqlalchemy import func, select


def test_production_world_bootstrap_is_idempotent() -> None:
    with SessionLocal() as db:
        bootstrap_world(db, get_settings())
        db.commit()
        bootstrap_world(db, get_settings())
        db.commit()

        world = db.scalar(select(World).where(World.slug == WORLD_SLUG))
        assert world is not None
        city = db.scalar(
            select(City).where(City.world_id == world.id, City.slug == START_CITY["slug"])
        )
        assert city is not None
        assert city.name == "Köln"
        assert db.scalar(select(func.count(District.id)).where(District.city_id == city.id)) == 5
        assert (
            db.scalar(select(func.count(WorldEvent.id)).where(WorldEvent.world_id == world.id))
            == 12
        )


def test_production_admin_bootstrap_is_idempotent() -> None:
    settings = get_settings().model_copy(
        update={
            "bootstrap_admin_email": "owner@example.com",
            "bootstrap_admin_password": SecretStr("ProductionPassword123!"),
        }
    )

    with SessionLocal() as db:
        bootstrap_admin(db, settings)
        db.commit()
        bootstrap_admin(db, settings)
        db.commit()

        users = list(db.scalars(select(User).where(User.email == "owner@example.com")))
        assert len(users) == 1
        assert users[0].email_verified is True
        assert users[0].is_admin is True
        assert users[0].is_moderator is True
