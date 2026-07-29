"""Initial photo gallery schema."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_name", sa.String(length=120), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="imagestatus"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("stored_filename"),
    )
    op.create_index("ix_photos_status", "photos", ["status"])
    op.create_index("ix_photos_user_name", "photos", ["user_name"])
    op.create_index("ix_photos_uploaded_at", "photos", ["uploaded_at"])

def downgrade() -> None:
    op.drop_index("ix_photos_uploaded_at", table_name="photos")
    op.drop_index("ix_photos_user_name", table_name="photos")
    op.drop_index("ix_photos_status", table_name="photos")
    op.drop_table("photos")
