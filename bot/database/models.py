import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PrintJobStatus(enum.Enum):
    PENDING = "PENDING"
    PRINTING = "PRINTING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class AssetType(enum.Enum):
    LOGO = "LOGO"
    QR_IOS = "QR_IOS"
    QR_ANDROID = "QR_ANDROID"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="user")


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_numbers: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[PrintJobStatus] = mapped_column(
        Enum(PrintJobStatus, name="print_job_status", native_enum=False),
        default=PrintJobStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    printed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="print_jobs")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type", native_enum=False),
        unique=True,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
