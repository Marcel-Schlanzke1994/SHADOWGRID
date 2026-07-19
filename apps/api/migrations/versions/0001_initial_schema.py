"""Create the initial server-authoritative schema."""

from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
