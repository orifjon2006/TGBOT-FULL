"""Admin ishlar — so'rovlar, amaldagi ishlar, statistika, tarix, eksport, buyurtma boshqarish."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update as sql_update

from config import (
    BTN_ACTIVE_JOBS,
    BTN_APPROVALS,
    BTN_BACK,
    BTN_EXPORT_EXCEL,
    BTN_ORDER_HISTORY,
    BTN_STATISTICS,
)
from database import (
    ActiveJobRepository,
    MasterGroup,
    MasterGroupRepository,
    Order,
    OrderRepository,
    User,
    UserRepository,
    UserRole,
    session_scope,
)
from keyboards import (
    single_active_job_kb,
    order_history_kb,
    order_manage_kb,
    pending_admin_actions_kb,
    pending_admins_kb,
    reassign_groups_kb,
    statistics_kb,
)
from services import build_all_orders_excel, build_receipt_file, build_stats_excel
from states import OrderManageStates
from utils import format_amount, html_escape, parse_amount, split_long_text

router = Router(name="admin")


async def safe_edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


# ═══════════════════════════════════════════════════════════════════════════
#  ADMIN SO'ROVLARI (APPROVAL)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_APPROVALS)
async def show_approvals(message: Message) -> None:
    from handlers.common import is_main_admin
    if not await is_main_admin(message.from_user.id):
        await message.answer("Bu bo'lim faqat asosiy admin uchun.")
        return
    async with session_scope() as s:
        pending = await UserRepository(s).get_pending_subadmins()
    text = "Kutayotgan so'rovlar:" if pending else "Hozircha kutayotgan so'rov yo'q."
    await message.answer(text, reply_markup=pending_admins_kb(pending))


@router.callback_query(F.data == "adm:list")
async def approvals_list_cb(cb: CallbackQuery) -> None:
    await cb.answer()
    async with session_scope() as s:
        pending = await UserRepository(s).get_pending_subadmins()
    text = "Kutayotgan so'rovlar:" if pending else "Hozircha kutayotgan so'rov yo'q."
    await safe_edit(cb, text, pending_admins_kb(pending))


@router.callback_query(F.data == "adm:back:menu")
async def approvals_back(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    from handlers.common import show_main_menu
    await show_main_menu(cb.message, cb.from_user.id)


@router.callback_query(F.data.startswith("adm:view:"))
async def approval_view(cb: CallbackQuery) -> None:
    await cb.answer()
    uid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        target = await s.get(User, uid)
    if not target:
        await cb.message.answer("❌ Topilmadi.")
        return
    text = (
        "<b>Qo'shimcha admin so'rovi</b>\n\n"
        f"<b>ID:</b> {target.id}\n"
        f"<b>Ism:</b> {html_escape(target.full_name)}\n"
        f"<b>Telefon:</b> {html_escape(target.phone_number or '—')}\n"
        f"<b>Telegram ID:</b> {target.telegram_id}"
    )
    await safe_edit(cb, text, pending_admin_actions_kb(target.id))


@router.callback_query(F.data.startswith("adm:approve:"))
async def approval_approve(cb: CallbackQuery) -> None:
    await cb.answer("Tasdiqlandi")
    uid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        repo = UserRepository(s)
        admin = await repo.get_by_telegram_id(cb.from_user.id)
        target = await repo.set_role(uid, UserRole.SUBADMIN, approved_by_id=admin.id if admin else None)
    if target:
        await cb.message.answer(f"✅ {target.full_name} endi qo'shimcha admin.")
    await approvals_list_cb(cb)


@router.callback_query(F.data.startswith("adm:reject:"))
async def approval_reject(cb: CallbackQuery) -> None:
    await cb.answer("Rad etildi")
    uid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        repo = UserRepository(s)
        target = await repo.set_role(uid, UserRole.USER)
    if target:
        await cb.message.answer(f"❌ {target.full_name} so'rovi rad etildi.")
    await approvals_list_cb(cb)


# ═══════════════════════════════════════════════════════════════════════════
#  AMALDAGI ISHLAR (ACTIVE JOBS)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_ACTIVE_JOBS)
async def show_active_jobs(message: Message) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return
    async with session_scope() as s:
        jobs = await ActiveJobRepository(s).get_all_active_jobs()
        if not jobs:
            await message.answer("🎉 Hozirda amaldagi xizmatlar yo'q.")
            return
            
        await message.answer("<b>🔧 Amaldagi xizmatlar:</b>")

        for job in jobs:
            order = await s.get(Order, job.order_id)
            if not order:
                continue
            gn = "—"
            if job.group_id:
                g = await s.get(MasterGroup, job.group_id)
                gn = g.name if g else "—"
            svcs = "\n".join(f"🔸 <i>{html_escape(x)}</i>" for x in order.service_names_list) or "—"
            at = job.assigned_at.strftime("%d.%m.%Y %H:%M") if job.assigned_at else "—"

            # Ish vaqti
            time_info = ""
            if job.started_at:
                elapsed = datetime.utcnow() - job.started_at
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                mins = remainder // 60
                time_info = f"\n⏱ <b>Boshlanganiga:</b>  <code>{hours} soat, {mins} daqiqa</code>"

            text = (
                f"🔖 <b>Zakaz №{order.order_number}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🚘 <b>Avtomobil:</b>  <code>{html_escape(order.vehicle_model or 'Nomalum')}</code>\n"
                f"👤 <b>Mijoz:</b>  <code>{html_escape(order.client_name)}</code> 📞 {html_escape(order.client_phone)}\n"
                f"🛠 <b>Zarur xizmatlar:</b>\n{svcs}\n\n"
                f"👥 <b>Hozirgi guruh:</b>  {html_escape(gn)}\n"
                f"📅 <b>Biriktirilgan vaqt:</b>  {at}{time_info}"
            )
            
            await message.answer(text, reply_markup=single_active_job_kb(job.id))


@router.callback_query(F.data.startswith("aj:re:"))
async def reassign_job(cb: CallbackQuery) -> None:
    await cb.answer()
    jid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        groups = await MasterGroupRepository(s).list_active()
    await safe_edit(cb, "Qaysi guruhga o'tkazmoqchisiz?", reassign_groups_kb(jid, groups))


@router.callback_query(F.data.startswith("aj:mv:"))
async def move_job(cb: CallbackQuery) -> None:
    await cb.answer("O'tkazildi")
    parts = cb.data.split(":")
    jid, ngid = int(parts[2]), int(parts[3])
    async with session_scope() as s:
        repo = ActiveJobRepository(s)
        await repo.reassign_job(jid, ngid)
        job = await repo.get_job_by_id(jid)
        if job:
            await s.execute(sql_update(Order).where(Order.id == job.order_id).values(assigned_group_id=ngid))
    await cb.message.answer("✅ Buyurtma boshqa guruhga o'tkazildi.")


# ═══════════════════════════════════════════════════════════════════════════
#  STATISTIKA
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_STATISTICS)
async def show_statistics(message: Message) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return
    await message.answer("📊 Statistika davrini tanlang:", reply_markup=statistics_kb())


@router.callback_query(F.data.startswith("stat:ex:"))
async def statistics_excel(cb: CallbackQuery) -> None:
    await cb.answer("Excel tayyorlanmoqda...")
    parts = cb.data.split(":")
    period = parts[2]
    group_id = int(parts[3])

    now = datetime.utcnow()
    if period == "today":
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label_base = "Bugun"
    elif period == "week":
        date_from = now - timedelta(days=now.weekday())
        date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
        label_base = "Bu hafta"
    elif period == "month":
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label_base = "Bu oy"
    else:
        date_from = datetime(2020, 1, 1)
        label_base = "Barcha vaqt"

    async with session_scope() as s:
        group_name = "Umumiy"
        if group_id != 0:
            g = await s.get(MasterGroup, group_id)
            if g:
                group_name = g.name
        label = f"{label_base} ({group_name})"
        
        stats = await OrderRepository(s).get_stats(date_from, now, group_id=None if group_id == 0 else group_id)

    file_path = build_stats_excel(stats, label)
    try:
        doc = FSInputFile(file_path)
        await cb.message.answer_document(document=doc, caption=f"📊 Statistika — {label}")
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.callback_query(F.data == "stat:back")
async def statistics_back(cb: CallbackQuery) -> None:
    await cb.answer()
    await safe_edit(cb, "📊 Statistika davrini tanlang:", statistics_kb())


@router.callback_query(F.data.startswith("stat:view:"))
async def statistics_period(cb: CallbackQuery) -> None:
    await cb.answer("Hisoblanmoqda...")
    parts = cb.data.split(":")
    period = parts[2]
    group_id = int(parts[3])

    now = datetime.utcnow()
    if period == "today":
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label_base = f"Bugun ({now.strftime('%d.%m.%Y')})"
    elif period == "week":
        date_from = now - timedelta(days=now.weekday())
        date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
        label_base = "Bu hafta"
    elif period == "month":
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label_base = f"Bu oy ({now.strftime('%m.%Y')})"
    else:  # all
        date_from = datetime(2020, 1, 1)
        label_base = "Barcha vaqt"

    async with session_scope() as s:
        groups = await MasterGroupRepository(s).list_active()
        group_name = "Umumiy"
        if group_id != 0:
            for g in groups:
                if g.id == group_id:
                    group_name = g.name
                    break
        label = f"{label_base} | {group_name}"
        
        stats = await OrderRepository(s).get_stats(date_from, now, group_id=None if group_id == 0 else group_id)

    # Matn statistika
    top_masters = sorted(stats["master_stats"].items(), key=lambda x: -x[1])[:10]
    top_services = sorted(stats["service_stats"].items(), key=lambda x: -x[1])[:10]

    masters_text = "\n".join(f"  {i}. {html_escape(n)} — {c} ta" for i, (n, c) in enumerate(top_masters, 1)) or "  —"
    services_text = "\n".join(f"  {i}. {html_escape(n)} — {c} ta" for i, (n, c) in enumerate(top_services, 1)) or "  —"

    text = (
        f"📊 <b>Statistika — {label}</b>\n\n"
        f"<b>Jami buyurtmalar:</b> {stats['total_count']} ta\n"
        f"🟢 Aktiv: {stats['active_count']}\n"
        f"✅ Bajarilgan: {stats['completed_count']}\n"
        f"🔴 Bekor: {stats['cancelled_count']}\n\n"
        f"<b>💰 Umumiy summa:</b> {format_amount(stats['total_amount'])}\n\n"
        f"<b>👨‍🔧 Top ustalar:</b>\n{masters_text}\n\n"
        f"<b>🛠 Top xizmatlar:</b>\n{services_text}"
    )

    from keyboards import statistics_result_kb
    markup = statistics_result_kb(period, groups, group_id)

    await safe_edit(cb, text, markup)


# ═══════════════════════════════════════════════════════════════════════════
#  BUYURTMALAR TARIXI
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_ORDER_HISTORY)
async def show_order_history(message: Message, state: FSMContext) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return
    async with session_scope() as s:
        orders = await OrderRepository(s).get_all_orders(limit=100)
    if not orders:
        await message.answer("📋 Buyurtmalar tarixi bo'sh.")
        return
    await state.update_data(history_orders_ids=[o.id for o in orders])
    await message.answer(
        f"📋 Buyurtmalar tarixi ({len(orders)} ta):",
        reply_markup=order_history_kb(orders, page=0),
    )


@router.callback_query(F.data.startswith("oh:page:"))
async def history_page(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    page = int(cb.data.split(":")[-1])
    data = await state.get_data()
    order_ids = data.get("history_orders_ids", [])

    async with session_scope() as s:
        orders = []
        for oid in order_ids:
            o = await s.get(Order, oid)
            if o:
                orders.append(o)

    await safe_edit(cb, f"📋 Buyurtmalar tarixi ({len(orders)} ta):", order_history_kb(orders, page=page))


@router.callback_query(F.data == "oh:list")
async def history_list(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    async with session_scope() as s:
        orders = await OrderRepository(s).get_all_orders(limit=100)
    await state.update_data(history_orders_ids=[o.id for o in orders])
    await safe_edit(cb, f"📋 Buyurtmalar tarixi ({len(orders)} ta):", order_history_kb(orders, page=0))


# ═══════════════════════════════════════════════════════════════════════════
#  BUYURTMA KO'RISH VA BOSHQARISH
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("oh:v:"))
async def order_view(cb: CallbackQuery) -> None:
    await cb.answer()
    oid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        order = await s.get(Order, oid)
    if not order:
        await cb.message.answer("❌ Topilmadi.")
        return

    svcs = ", ".join(order.service_names_list) or "—"
    masters = ", ".join(order.master_names_list) or "—"
    status_text = {"active": "🟢 Aktiv", "completed": "✅ Bajarilgan", "cancelled": "🔴 Bekor"}.get(
        order.status or "active", "—"
    )

    # Litsenziya ma'lumotini tekshirish
    lic_info = ""
    async with session_scope() as s:
        from database import License
        from sqlalchemy import select
        # Order ID yoki VIN orqali qidiramiz
        q = select(License).where((License.order_id == oid) | (License.vin_code == order.vin))
        res = await s.execute(q)
        lic = res.scalar_one_or_none()
        if lic:
            lic_info = f"\n📜 <b>Litsenziya:</b> {lic.issuance_date} gacha tayyor."

    text = (
        f"<b>📋 Buyurtma №{order.order_number}</b>\n\n"
        f"<b>Holat:</b> {status_text}\n"
        f"<b>Sana:</b> {order.confirmed_at.strftime('%d.%m.%Y %H:%M') if order.confirmed_at else '—'}\n"
        f"<b>Mijoz:</b> {html_escape(order.client_name)}\n"
        f"<b>Telefon:</b> {html_escape(order.client_phone)}\n"
        f"<b>Model:</b> {html_escape(order.vehicle_model_name_snapshot)}\n"
        f"<b>VIN:</b> {html_escape(order.vin_code or '—')}\n"
        f"<b>Xizmatlar:</b> {html_escape(svcs)}\n"
        f"<b>Summa:</b> {format_amount(order.total_amount)}\n"
        f"<b>Balandlik:</b> {html_escape(order.van_height_name_snapshot)}\n"
        f"<b>Ustalar:</b> {html_escape(masters)}"
        f"{lic_info}"
    )
    if order.comment:
        text += f"\n\n<b>📝 Izohlar:</b>\n{html_escape(order.comment)}"

    is_active = (order.status or "active") == "active"
    vin = order.vin_code or ""
    # Agar VIN yo'q bo'lsa, litsenziya tugmasi "order_id" orqali ishlashi uchun "oid" uzatamiz (ixtiyoriy)
    # Hozircha vin="" bo'lsa keyboards.py dagi tugma chiqmaydi. 
    # Men uni har doim chiqadigan qilaman.
    await safe_edit(cb, text, order_manage_kb(oid, is_active, vin=vin or f"order_{oid}"))


# ── Summani o'zgartirish
@router.callback_query(F.data.startswith("om:amount:"))
async def order_edit_amount(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    oid = int(cb.data.split(":")[-1])
    await state.update_data(editing_order_id=oid)
    await state.set_state(OrderManageStates.waiting_edit_amount)
    await cb.message.answer("💰 Yangi summani kiriting:", reply_markup=ReplyKeyboardRemove())


@router.message(OrderManageStates.waiting_edit_amount)
async def order_edit_amount_process(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_amount(message.text or "")
    except ValueError as e:
        await message.answer(str(e))
        return

    data = await state.get_data()
    oid = data.get("editing_order_id")
    async with session_scope() as s:
        order = await OrderRepository(s).update_order_amount(oid, int(amount))

    await state.clear()
    if order:
        await message.answer(f"✅ Summa yangilandi: {format_amount(order.total_amount)}")
    else:
        await message.answer("❌ Buyurtma topilmadi.")
    from handlers.common import show_main_menu
    await show_main_menu(message, message.from_user.id)


# ── Izoh qo'shish
@router.callback_query(F.data.startswith("om:comment:"))
async def order_add_comment(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    oid = int(cb.data.split(":")[-1])
    await state.update_data(editing_order_id=oid)
    await state.set_state(OrderManageStates.waiting_comment)
    await cb.message.answer("📝 Izoh matnini kiriting:", reply_markup=ReplyKeyboardRemove())


@router.message(OrderManageStates.waiting_comment)
async def order_add_comment_process(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("❌ Izoh bo'sh.")
        return

    data = await state.get_data()
    oid = data.get("editing_order_id")
    async with session_scope() as s:
        order = await OrderRepository(s).add_comment(oid, comment)

    await state.clear()
    if order:
        await message.answer("✅ Izoh qo'shildi.")
    else:
        await message.answer("❌ Buyurtma topilmadi.")
    from handlers.common import show_main_menu
    await show_main_menu(message, message.from_user.id)


# ── Bekor qilish
@router.callback_query(F.data.startswith("om:cancel:"))
async def order_cancel(cb: CallbackQuery) -> None:
    await cb.answer("Bekor qilinmoqda...")
    oid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        order = await OrderRepository(s).cancel_order(oid)
        # Aktiv jobni ham bekor qilish
        if order:
            jobs = await s.execute(
                select(ActiveJobRepository.__class__)
            )
            from database import ActiveJob
            result = await s.execute(
                select(ActiveJob).where(ActiveJob.order_id == oid, ActiveJob.status == "in_progress")
            )
            for job in result.scalars():
                job.status = "cancelled"
            await s.flush()

    if order:
        await cb.message.answer(f"🔴 Buyurtma №{order.order_number} bekor qilindi.")
    else:
        await cb.message.answer("❌ Topilmadi.")


# ── Chek yuklab olish
@router.callback_query(F.data.startswith("om:receipt:"))
async def order_download_receipt(cb: CallbackQuery) -> None:
    await cb.answer("Chek tayyorlanmoqda...")
    oid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        order = await s.get(Order, oid)
    if not order:
        await cb.message.answer("❌ Topilmadi.")
        return

    service_names = order.service_names_list
    master_names = order.master_names_list
    file_path = build_receipt_file(order, service_names, master_names)
    try:
        doc = FSInputFile(file_path)
        await cb.message.answer_document(
            document=doc,
            caption=f"📄 Chek — Zakaz №{order.order_number}",
        )
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  EXCEL EKSPORT (barcha buyurtmalar)
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_EXPORT_EXCEL)
async def export_excel(message: Message) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return

    async with session_scope() as s:
        orders = await OrderRepository(s).get_all_orders(limit=500)

    if not orders:
        await message.answer("📤 Eksport qilish uchun buyurtmalar yo'q.")
        return

    file_path = build_all_orders_excel(orders)
    try:
        doc = FSInputFile(file_path)
        await message.answer_document(
            document=doc,
            caption=f"📤 Barcha buyurtmalar ({len(orders)} ta)",
        )
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
