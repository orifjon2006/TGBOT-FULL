"""Ma'lumotlar bazasi modellari va repository-lar.

Yangi maydonlar: Order.status, Order.comment, Order.updated_at
Migratsiya yordamchisi mavjud borlar uchun.
"""

from __future__ import annotations

import json
import random
import string
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
    text,
    update as sql_update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./database.db")


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ═══════════════════════════════════════════════════════════════════════════
#  Rollar
# ═══════════════════════════════════════════════════════════════════════════

class UserRole:
    MAIN_ADMIN = "main_admin"
    SUB_ADMIN = "sub_admin"
    GUEST = "guest"
    PENDING_SUBADMIN = "pending_subadmin"

    # Qisqa alias-lar
    ADMIN = MAIN_ADMIN
    SUBADMIN = SUB_ADMIN
    USER = GUEST


# ═══════════════════════════════════════════════════════════════════════════
#  Modellar
# ═══════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.GUEST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    @property
    def phone_number(self) -> Optional[str]:
        return self.phone

    @phone_number.setter
    def phone_number(self, value: Optional[str]) -> None:
        self.phone = value


class VehicleModel(Base):
    __tablename__ = "vehicle_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class VanHeight(Base):
    __tablename__ = "van_heights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MasterGroup(Base):
    """Ustalar guruhi — admin tomonidan yaratiladi."""
    __tablename__ = "master_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Master(Base):
    __tablename__ = "masters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("master_groups.id"), nullable=True
    )
    telegram_id: Mapped[Optional[int]] = mapped_column(
        Integer, unique=True, nullable=True, index=True
    )
    access_code: Mapped[Optional[str]] = mapped_column(
        String(6), unique=True, nullable=True
    )

    @property
    def phone_number(self) -> Optional[str]:
        return self.phone

    @phone_number.setter
    def phone_number(self, value: Optional[str]) -> None:
        self.phone = value


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    label: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vin_code: Mapped[Optional[str]] = mapped_column(String(100), index=True, unique=True, nullable=True)
    client_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    client_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    applied_date: Mapped[str] = mapped_column(String(255))
    issuance_date: Mapped[str] = mapped_column(String(255))
    order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    application_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_name: Mapped[str] = mapped_column(String(255))
    client_phone: Mapped[str] = mapped_column(String(20))
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    services: Mapped[str] = mapped_column(Text)        # JSON — xizmat nomlari
    total_amount: Mapped[int] = mapped_column(Integer)  # tiyinlarda
    van_height: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    masters: Mapped[str] = mapped_column(Text)          # JSON — usta nomlari
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    # Guruhga tayinlash
    assigned_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("master_groups.id"), nullable=True
    )

    # ── YANGI MAYDONLAR ──
    access_code: Mapped[Optional[str]] = mapped_column(String(5), unique=True, index=True, nullable=True)
    client_telegram_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(
        String(20), default="active", nullable=True
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)

    # ── Mos xususiyatlar ──

    @property
    def order_number(self) -> int:
        return self.id

    @property
    def confirmed_at(self):
        return self.created_at

    @property
    def vehicle_model_name_snapshot(self) -> str:
        return self.vehicle_model or "—"

    @property
    def vin_code(self) -> Optional[str]:
        return self.vin

    @property
    def van_height_name_snapshot(self) -> str:
        return self.van_height or "—"

    @property
    def service_names_list(self) -> list[str]:
        try:
            return json.loads(self.services) if self.services else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def master_names_list(self) -> list[str]:
        try:
            return json.loads(self.masters) if self.masters else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def is_active_order(self) -> bool:
        return (self.status or "active") == "active"

    @property
    def is_cancelled(self) -> bool:
        return (self.status or "") == "cancelled"

    @property
    def status_emoji(self) -> str:
        s = self.status or "active"
        return {"active": "🟢", "completed": "✅", "cancelled": "🔴"}.get(s, "⚪")


class ActiveJob(Base):
    """Hozirda bajarilayotgan ish — usta uchun."""
    __tablename__ = "active_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("master_groups.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    assigned_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    completed_by_master_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("masters.id"), nullable=True
    )
    completion_video_file_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    # Ish boshlangan vaqt (usta «Boshlash» bosganda)
    started_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
#  DTO va Xatoliklar
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CreateOrderDTO:
    client_name: str
    client_phone: str
    total_amount: int
    created_by_user_id: int
    confirmed_by_user_id: int
    service_ids: list[Any] = field(default_factory=list)
    master_ids: list[Any] = field(default_factory=list)
    vehicle_model_id: Optional[int] = None
    custom_vehicle_model_name: Optional[str] = None
    vin_code: Optional[str] = None
    van_height_id: Optional[int] = None
    assigned_group_id: Optional[int] = None
    comment: Optional[str] = None


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


# ═══════════════════════════════════════════════════════════════════════════
#  Yordamchi
# ═══════════════════════════════════════════════════════════════════════════

def generate_access_code() -> str:
    return "".join(random.choices(string.digits, k=6))


# ═══════════════════════════════════════════════════════════════════════════
#  Repository-lar
# ═══════════════════════════════════════════════════════════════════════════

class BaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session


# ───────────────────────────────────────────────────────────────────────────
#  UserRepository
# ───────────────────────────────────────────────────────────────────────────

class UserRepository(BaseRepository):

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_user(
        self,
        telegram_id: int,
        full_name: str,
        role: str,
        phone_number: Optional[str] = None,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            phone=phone_number,
            role=role,
        )
        return await self.create(user)

    async def update_role(self, telegram_id: int, role: str) -> None:
        await self.session.execute(
            sql_update(User)
            .where(User.telegram_id == telegram_id)
            .values(role=role)
        )

    async def set_role(
        self, user_id: int, role: str, approved_by_id: Optional[int] = None
    ) -> Optional[User]:
        user = await self.session.get(User, user_id)
        if user:
            user.role = role
            await self.session.flush()
            return user
        user = await self.get_by_telegram_id(user_id)
        if user:
            user.role = role
            await self.session.flush()
        return user

    async def get_pending_subadmins(self) -> List[User]:
        result = await self.session.execute(
            select(User)
            .where(User.role == UserRole.PENDING_SUBADMIN, User.is_active.is_(True))
            .order_by(User.created_at.asc())
        )
        return list(result.scalars())


# ───────────────────────────────────────────────────────────────────────────
#  VehicleModelRepository
# ───────────────────────────────────────────────────────────────────────────

class VehicleModelRepository(BaseRepository):

    async def get_all_active(self) -> List[VehicleModel]:
        result = await self.session.execute(
            select(VehicleModel)
            .where(VehicleModel.is_active.is_(True))
            .order_by(VehicleModel.sort_order)
        )
        return list(result.scalars())

    async def list_active(self) -> List[VehicleModel]:
        return await self.get_all_active()

    async def get_by_id(self, id: int) -> Optional[VehicleModel]:
        return await self.session.get(VehicleModel, id)

    async def create(self, name: str) -> VehicleModel:
        model = VehicleModel(name=name)
        self.session.add(model)
        await self.session.flush()
        return model

    async def add(self, name: str, phone: Optional[str] = None) -> VehicleModel:
        return await self.create(name)

    async def update(self, item_id: int, **kwargs: Any) -> None:
        values = {k: v for k, v in kwargs.items() if k in ("name", "sort_order", "is_active")}
        if values:
            await self.session.execute(
                sql_update(VehicleModel).where(VehicleModel.id == item_id).values(**values)
            )


# ───────────────────────────────────────────────────────────────────────────
#  VanHeightRepository
# ───────────────────────────────────────────────────────────────────────────

class VanHeightRepository(BaseRepository):

    async def get_all_active(self) -> List[VanHeight]:
        result = await self.session.execute(
            select(VanHeight)
            .where(VanHeight.is_active.is_(True))
            .order_by(VanHeight.sort_order)
        )
        return list(result.scalars())

    async def list_active(self) -> List[VanHeight]:
        return await self.get_all_active()

    async def get_by_id(self, id: int) -> Optional[VanHeight]:
        return await self.session.get(VanHeight, id)

    async def create(self, name: str) -> VanHeight:
        height = VanHeight(name=name)
        self.session.add(height)
        await self.session.flush()
        return height

    async def add(self, name: str, phone: Optional[str] = None) -> VanHeight:
        return await self.create(name)

    async def update(self, item_id: int, **kwargs: Any) -> None:
        values = {k: v for k, v in kwargs.items() if k in ("name", "sort_order", "is_active")}
        if values:
            await self.session.execute(
                sql_update(VanHeight).where(VanHeight.id == item_id).values(**values)
            )


# ───────────────────────────────────────────────────────────────────────────
#  MasterGroupRepository
# ───────────────────────────────────────────────────────────────────────────

class MasterGroupRepository(BaseRepository):

    async def get_all_active(self) -> List[MasterGroup]:
        result = await self.session.execute(
            select(MasterGroup)
            .where(MasterGroup.is_active.is_(True))
            .order_by(MasterGroup.name)
        )
        return list(result.scalars())

    async def list_active(self) -> List[MasterGroup]:
        return await self.get_all_active()

    async def get_by_id(self, group_id: int) -> Optional[MasterGroup]:
        return await self.session.get(MasterGroup, group_id)

    async def create(self, name: str) -> MasterGroup:
        group = MasterGroup(name=name)
        self.session.add(group)
        await self.session.flush()
        return group

    async def update(self, group_id: int, **kwargs: Any) -> None:
        values = {k: v for k, v in kwargs.items() if k in ("name", "is_active")}
        if values:
            await self.session.execute(
                sql_update(MasterGroup).where(MasterGroup.id == group_id).values(**values)
            )

    async def delete(self, group_id: int) -> None:
        await self.session.execute(
            sql_update(MasterGroup).where(MasterGroup.id == group_id).values(is_active=False)
        )

    async def get_masters_in_group(self, group_id: int) -> List[Master]:
        result = await self.session.execute(
            select(Master)
            .where(Master.group_id == group_id, Master.is_active.is_(True))
            .order_by(Master.sort_order)
        )
        return list(result.scalars())


# ───────────────────────────────────────────────────────────────────────────
#  MasterRepository
# ───────────────────────────────────────────────────────────────────────────

class MasterRepository(BaseRepository):

    async def get_all_active(self) -> List[Master]:
        result = await self.session.execute(
            select(Master)
            .where(Master.is_active.is_(True))
            .order_by(Master.sort_order)
        )
        return list(result.scalars())

    async def list_active(self) -> List[Master]:
        return await self.get_all_active()

    async def get_by_id(self, id: int) -> Optional[Master]:
        return await self.session.get(Master, id)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Master]:
        result = await self.session.execute(
            select(Master).where(Master.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_access_code(self, code: str) -> Optional[Master]:
        result = await self.session.execute(
            select(Master).where(Master.access_code == code, Master.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def create(self, full_name: str, phone: Optional[str] = None) -> Master:
        code = generate_access_code()
        for _ in range(10):
            existing = await self.get_by_access_code(code)
            if not existing:
                break
            code = generate_access_code()

        master = Master(full_name=full_name, phone=phone, access_code=code)
        self.session.add(master)
        await self.session.flush()
        return master

    async def add(self, name: str, phone: Optional[str] = None) -> Master:
        return await self.create(full_name=name, phone=phone)

    async def update(self, item_id: int, **kwargs: Any) -> None:
        values = {}
        for k, v in kwargs.items():
            if k == "name":
                values["full_name"] = v
            elif k == "full_name":
                values["full_name"] = v
            elif k in ("phone", "phone_number"):
                values["phone"] = v
            elif k in ("sort_order", "is_active", "group_id", "telegram_id", "access_code"):
                values[k] = v
        if values:
            await self.session.execute(
                sql_update(Master).where(Master.id == item_id).values(**values)
            )

    async def set_group(self, master_id: int, group_id: Optional[int]) -> None:
        await self.session.execute(
            sql_update(Master).where(Master.id == master_id).values(group_id=group_id)
        )

    async def link_telegram(self, master_id: int, telegram_id: int) -> None:
        await self.session.execute(
            sql_update(Master)
            .where(Master.id == master_id)
            .values(telegram_id=telegram_id)
        )


# ───────────────────────────────────────────────────────────────────────────
#  ServiceRepository
# ───────────────────────────────────────────────────────────────────────────

class ServiceRepository(BaseRepository):

    async def get_all_active(self) -> List[ServiceCatalog]:
        result = await self.session.execute(
            select(ServiceCatalog)
            .where(ServiceCatalog.is_active.is_(True))
            .order_by(ServiceCatalog.sort_order)
        )
        return list(result.scalars())

    async def list_active(self) -> List[ServiceCatalog]:
        return await self.get_all_active()

    async def get_by_id(self, id: int) -> Optional[ServiceCatalog]:
        return await self.session.get(ServiceCatalog, id)

    async def create(self, key: str, label: str) -> ServiceCatalog:
        service = ServiceCatalog(key=key, label=label)
        self.session.add(service)
        await self.session.flush()
        return service

    async def add(self, name: str, phone: Optional[str] = None) -> ServiceCatalog:
        return await self.create(key=str(uuid.uuid4()), label=name)

    async def update(self, item_id: int, **kwargs: Any) -> None:
        values = {}
        for k, v in kwargs.items():
            if k in ("name", "label"):
                values["label"] = v
            elif k in ("sort_order", "is_active"):
                values[k] = v
        if values:
            await self.session.execute(
                sql_update(ServiceCatalog)
                .where(ServiceCatalog.id == item_id)
                .values(**values)
            )


# ───────────────────────────────────────────────────────────────────────────
#  ActiveJobRepository
# ───────────────────────────────────────────────────────────────────────────

class ActiveJobRepository(BaseRepository):

    async def create_job(
        self, order_id: int, group_id: Optional[int] = None
    ) -> ActiveJob:
        job = ActiveJob(order_id=order_id, group_id=group_id, status="in_progress")
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_active_jobs_for_group(self, group_id: int) -> List[ActiveJob]:
        result = await self.session.execute(
            select(ActiveJob)
            .where(ActiveJob.group_id == group_id, ActiveJob.status == "in_progress")
            .order_by(ActiveJob.assigned_at.desc())
        )
        return list(result.scalars())

    async def get_active_jobs_for_master(self, master_id: int) -> List[ActiveJob]:
        """Usta guruhiga tayinlangan barcha aktiv ishlar."""
        master = await self.session.get(Master, master_id)
        if not master or not master.group_id:
            return []
        return await self.get_active_jobs_for_group(master.group_id)

    async def get_active_jobs_for_master_by_telegram(
        self, telegram_id: int
    ) -> List[ActiveJob]:
        result = await self.session.execute(
            select(Master).where(Master.telegram_id == telegram_id)
        )
        master = result.scalar_one_or_none()
        if not master or not master.group_id:
            return []
        return await self.get_active_jobs_for_group(master.group_id)

    async def get_all_active_jobs(self) -> List[ActiveJob]:
        result = await self.session.execute(
            select(ActiveJob)
            .where(ActiveJob.status == "in_progress")
            .order_by(ActiveJob.assigned_at.desc())
        )
        return list(result.scalars())

    async def get_job_by_id(self, job_id: int) -> Optional[ActiveJob]:
        return await self.session.get(ActiveJob, job_id)

    async def complete_job(
        self,
        job_id: int,
        completed_by_master_id: int,
        video_file_id: Optional[str] = None,
    ) -> Optional[ActiveJob]:
        job = await self.session.get(ActiveJob, job_id)
        if not job:
            return None
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.completed_by_master_id = completed_by_master_id
        job.completion_video_file_id = video_file_id
        await self.session.flush()
        return job

    async def start_job(self, job_id: int) -> Optional[ActiveJob]:
        """Usta ishni boshlash — vaqtni qayd etish."""
        job = await self.session.get(ActiveJob, job_id)
        if not job:
            return None
        job.started_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def reassign_job(self, job_id: int, new_group_id: int) -> Optional[ActiveJob]:
        job = await self.session.get(ActiveJob, job_id)
        if not job:
            return None
        job.group_id = new_group_id
        await self.session.flush()
        return job

    async def get_order_for_job(self, job_id: int) -> Optional[Order]:
        job = await self.session.get(ActiveJob, job_id)
        if not job:
            return None
        return await self.session.get(Order, job.order_id)


# ───────────────────────────────────────────────────────────────────────────
#  OrderRepository
# ───────────────────────────────────────────────────────────────────────────

class OrderRepository(BaseRepository):

    async def create_order(self, dto: CreateOrderDTO) -> Order:
        vehicle_model_str = dto.custom_vehicle_model_name
        if not vehicle_model_str and dto.vehicle_model_id:
            model = await self.session.get(VehicleModel, dto.vehicle_model_id)
            if model:
                vehicle_model_str = model.name

        van_height_str = None
        if dto.van_height_id:
            height = await self.session.get(VanHeight, dto.van_height_id)
            if height:
                van_height_str = height.name

        try:
            amount = int(dto.total_amount)
        except (TypeError, ValueError):
            amount = int(float(str(dto.total_amount)))

        import random
        import string
        from sqlalchemy import select

        code = None
        for _ in range(10):
            cand = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            res = await self.session.execute(select(Order).where(Order.access_code == cand))
            if not res.scalar_one_or_none():
                code = cand
                break
        if not code:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

        order = Order(
            client_name=dto.client_name,
            client_phone=dto.client_phone,
            vehicle_model=vehicle_model_str,
            vin=dto.vin_code,
            services=json.dumps(dto.service_ids, ensure_ascii=False),
            total_amount=amount,
            van_height=van_height_str,
            masters=json.dumps(dto.master_ids, ensure_ascii=False),
            created_by=dto.created_by_user_id,
            assigned_group_id=dto.assigned_group_id,
            status="active",
            comment=dto.comment,
            access_code=code,
        )
        self.session.add(order)
        await self.session.flush()
        await self.session.refresh(order)
        return order

    async def get_orders_by_client_phone(self, phone: str) -> List[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.client_phone == phone)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars())

    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        return await self.session.get(Order, order_id)

    async def get_all_orders(self, limit: int = 50) -> List[Order]:
        """Barcha buyurtmalar (tartib: oxirgisi birinchi)."""
        result = await self.session.execute(
            select(Order)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def get_active_orders(self, limit: int = 50) -> List[Order]:
        """Faqat aktiv buyurtmalar."""
        result = await self.session.execute(
            select(Order)
            .where(Order.status == "active")
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def cancel_order(self, order_id: int) -> Optional[Order]:
        """Buyurtmani bekor qilish."""
        order = await self.session.get(Order, order_id)
        if not order:
            return None
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        await self.session.flush()
        return order

    async def update_order_amount(self, order_id: int, new_amount: int) -> Optional[Order]:
        """Buyurtma summasini o'zgartirish."""
        order = await self.session.get(Order, order_id)
        if not order:
            return None
        order.total_amount = new_amount
        order.updated_at = datetime.utcnow()
        await self.session.flush()
        return order

    async def add_comment(self, order_id: int, comment_text: str) -> Optional[Order]:
        """Buyurtmaga izoh qo'shish."""
        order = await self.session.get(Order, order_id)
        if not order:
            return None
        existing = order.comment or ""
        timestamp = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
        new_comment = f"[{timestamp}] {comment_text}"
        order.comment = f"{existing}\n{new_comment}".strip() if existing else new_comment
        order.updated_at = datetime.utcnow()
        await self.session.flush()
        return order

    async def search_orders(
        self,
        query: str,
        search_type: str = "phone",
        limit: int = 50,
    ) -> List[Order]:
        """Kengaytirilgan qidiruv — telefon, ism, model, VIN bo'yicha."""
        q = query.strip()
        if search_type == "phone":
            stmt = select(Order).where(Order.client_phone.contains(q))
        elif search_type == "name":
            stmt = select(Order).where(Order.client_name.ilike(f"%{q}%"))
        elif search_type == "model":
            stmt = select(Order).where(Order.vehicle_model.ilike(f"%{q}%"))
        elif search_type == "vin":
            stmt = select(Order).where(Order.vin.ilike(f"%{q}%"))
        else:
            stmt = select(Order).where(Order.client_phone.contains(q))

        result = await self.session.execute(
            stmt.order_by(Order.created_at.desc()).limit(limit)
        )
        return list(result.scalars())

    async def get_stats(self, date_from: datetime, date_to: datetime, group_id: Optional[int] = None) -> dict:
        """Berilgan davr uchun statistika (va ixtiyoriy ravishda guruh bo'yicha)."""
        stmt = select(Order).where(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
        )
        if group_id is not None:
            stmt = stmt.where(Order.assigned_group_id == group_id)
            
        result = await self.session.execute(stmt)
        orders = list(result.scalars())

        total_count = len(orders)
        active_count = sum(1 for o in orders if (o.status or "active") == "active")
        cancelled_count = sum(1 for o in orders if (o.status or "") == "cancelled")
        completed_count = sum(1 for o in orders if (o.status or "") == "completed")
        total_amount = sum(o.total_amount for o in orders if (o.status or "active") != "cancelled")

        # Usta bo'yicha statistika
        master_stats: dict[str, int] = {}
        for o in orders:
            if (o.status or "active") == "cancelled":
                continue
            for m in o.master_names_list:
                master_stats[m] = master_stats.get(m, 0) + 1

        # Xizmat bo'yicha statistika
        service_stats: dict[str, int] = {}
        for o in orders:
            if (o.status or "active") == "cancelled":
                continue
            for s in o.service_names_list:
                service_stats[s] = service_stats.get(s, 0) + 1

        return {
            "total_count": total_count,
            "active_count": active_count,
            "cancelled_count": cancelled_count,
            "completed_count": completed_count,
            "total_amount": total_amount,
            "master_stats": master_stats,
            "service_stats": service_stats,
            "orders": orders,
        }


class LicenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        applied_date: str,
        issuance_date: str,
        vin_code: Optional[str] = None,
        client_name: str = "",
        client_phone: str = "",
        order_id: Optional[int] = None,
        application_number: Optional[str] = None,
    ) -> License:
        item = License(
            vin_code=vin_code,
            applied_date=applied_date,
            issuance_date=issuance_date,
            client_name=client_name,
            client_phone=client_phone,
            order_id=order_id,
            application_number=application_number,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def get_by_vin(self, vin: str) -> Optional[License]:
        from sqlalchemy import select
        res = await self._session.execute(select(License).where(License.vin_code == vin))
        return res.scalar_one_or_none()

    async def get_by_order_id(self, order_id: int) -> Optional[License]:
        from sqlalchemy import select
        res = await self._session.execute(select(License).where(License.order_id == order_id))
        return res.scalar_one_or_none()

    async def link_to_order(self, lic_id: int, order_id: int) -> None:
        from sqlalchemy import update as sql_update
        await self._session.execute(
            sql_update(License).where(License.id == lic_id).values(order_id=order_id)
        )
        await self._session.flush()

    async def search_by_vin_partial(self, search_val: str) -> list[License]:
        from sqlalchemy import select, or_
        res = await self._session.execute(
            select(License).where(
                or_(
                    License.vin_code.ilike(f"%{search_val}%"),
                    License.application_number.ilike(f"%{search_val}%")
                )
            )
        )
        return list(res.scalars().all())


# ═══════════════════════════════════════════════════════════════════════════
#  DB init va migratsiya
# ═══════════════════════════════════════════════════════════════════════════

async def _add_column_if_missing(conn, table: str, column: str, col_type: str, default=None):
    """Mavjud jadvalga yangi ustun qo'shish (agar yo'q bo'lsa)."""
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result]
    if column not in columns:
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        if default is not None:
            sql += f" DEFAULT '{default}'"
        await conn.execute(text(sql))


async def _fix_licenses_table_if_broken(conn) -> None:
    """licenses jadvalida 'key' ustuni bo'lsa, eski noto'g'ri jadval.
    Uni yangi to'g'ri sxemaga ko'chirish."""
    try:
        result = await conn.execute(text("PRAGMA table_info(licenses)"))
        cols = [row[1] for row in result]
        if "key" in cols:
            # Avvalgi ma'lumotlarni saqlab, jadvalni qayta qurish
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS licenses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin_code TEXT UNIQUE,
                    client_name TEXT,
                    client_phone TEXT,
                    applied_date TEXT NOT NULL,
                    issuance_date TEXT NOT NULL,
                    order_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            # Eski ma'lumotlarni ko'chirish
            await conn.execute(text("""
                INSERT OR IGNORE INTO licenses_new
                    (id, vin_code, client_name, client_phone, applied_date, issuance_date, order_id, created_at)
                SELECT id, vin_code, client_name, client_phone, applied_date, issuance_date, 
                       CASE WHEN (SELECT 1 FROM pragma_table_info('licenses') WHERE name='order_id') THEN order_id ELSE NULL END,
                       created_at
                FROM licenses
                WHERE (vin_code IS NOT NULL OR 1=1) AND applied_date IS NOT NULL AND issuance_date IS NOT NULL
            """))
            await conn.execute(text("DROP TABLE licenses"))
            await conn.execute(text("ALTER TABLE licenses_new RENAME TO licenses"))
    except Exception as e:
        pass  # Jadval yo'q bo'lsa yoki boshqa muammo — create_all hal qiladi


async def init_db() -> None:
    async with engine.begin() as conn:
        # Avval siniq licenses jadvalini tuzatamiz (agar noto'g'ri bo'lsa)
        await _fix_licenses_table_if_broken(conn)

        await conn.run_sync(Base.metadata.create_all)

        # Mavjud bazaga yangi ustunlarni qo'shish
        await _add_column_if_missing(conn, "orders", "status", "VARCHAR(20)", "active")
        await _add_column_if_missing(conn, "orders", "comment", "TEXT")
        await _add_column_if_missing(conn, "orders", "updated_at", "DATETIME")
        await _add_column_if_missing(conn, "active_jobs", "started_at", "DATETIME")
        await _add_column_if_missing(conn, "licenses", "order_id", "INTEGER")
        await _add_column_if_missing(conn, "licenses", "application_number", "VARCHAR(50)")

    async with session_scope() as session:
        vehicle_repo = VehicleModelRepository(session)
        height_repo = VanHeightRepository(session)
        service_repo = ServiceRepository(session)

        if not await vehicle_repo.get_all_active():
            for name in [
                "Labo", "Changan", "Shinerey T30", "Shinerey T32",
                "Kia Bongo", "Kama", "Shinerey T50", "Gazel 220",
            ]:
                await vehicle_repo.create(name)

        if not await height_repo.get_all_active():
            for name in [
                "1.45", "1.50", "1.55", "1.60", "1.65", "1.70", "1.75",
                "1.80", "1.85", "1.90", "1.95", "2.00", "2.10", "2.20",
            ]:
                await height_repo.create(name)

        if not await service_repo.get_all_active():
            from config import DEFAULT_SIMPLE_SERVICES
            for svc in DEFAULT_SIMPLE_SERVICES:
                await service_repo.create(svc["key"], svc["label"])