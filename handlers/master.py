"""Usta interfeysi — kod kiritish, ishlar ko'rish, vaqt hisobi, yakunlash."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from config import BTN_CANCEL, COMPLETION_REPORT_CHAT_ID
from database import (
    ActiveJobRepository,
    MasterRepository,
    Order,
    Master,
    session_scope,
)
from keyboards import master_home_kb, master_job_detail_kb, master_jobs_kb
from services import send_completion_report
from states import MasterStates
from utils import html_escape

router = Router(name="master")


async def safe_edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


async def get_linked_master(tg_id: int) -> Master | None:
    async with session_scope() as s:
        return await MasterRepository(s).get_by_telegram_id(tg_id)


async def show_master_home(msg: Message) -> None:
    await msg.answer("🏠 Usta paneli. Ishlaringizni ko'ring.", reply_markup=master_home_kb())


# ═══════════════════════════════════════════════════════════════════════════
#  KOD KIRITISH — birinchi marta kirgan usta
# ═══════════════════════════════════════════════════════════════════════════

@router.message(MasterStates.waiting_access_code, F.text == BTN_CANCEL)
async def master_code_cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())


@router.message(MasterStates.waiting_access_code)
async def master_code_process(msg: Message, state: FSMContext) -> None:
    code = (msg.text or "").strip().upper()
    
    if len(code) == 6 and code.isdigit():
        async with session_scope() as s:
            repo = MasterRepository(s)
            master = await repo.get_by_access_code(code)
            if not master:
                await msg.answer("❌ Noto'g'ri kod. Usta yoki mijoz kodingizni tekshiring.")
                return
            if master.telegram_id and master.telegram_id != msg.from_user.id:
                await msg.answer("❌ Bu usta kodi boshqa foydalanuvchiga bog'langan.")
                return
            await repo.link_telegram(master.id, msg.from_user.id)

        await state.clear()
        await msg.answer(
            f"✅ Siz <b>{master.full_name}</b> sifatida ro'yxatdan o'tdingiz!",
            reply_markup=ReplyKeyboardRemove(),
        )
        await show_master_home(msg)
        return

    elif len(code) == 5:
        from database import Order
        from sqlalchemy import select
        from utils import format_amount

        async with session_scope() as s:
            res = await s.execute(select(Order).where(Order.access_code == code))
            order = res.scalar_one_or_none()
            if not order:
                await msg.answer("Iltimos, kodingizni to'g'ri kiriting. Buyurtma topilmadi.")
                return

            if order.client_telegram_id != msg.from_user.id:
                order.client_telegram_id = msg.from_user.id
                await s.flush()

            status_map = {
                "active": "🛠 Bajarilmoqda",
                "completed": "✅ Yakunlangan",
                "cancelled": "❌ Bekor qilingan",
                "closed": "📦 Yopilgan"
            }
            s_text = status_map.get(order.status, order.status or "🛠 Bajarilmoqda")

            svcs = "\n".join(f"🔸 {x}" for x in order.service_names_list) or "—"
            ans = (
                f"🌟 <b>LIDER AVTO 555</b> 🌟\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🚘 <b>Avtomobil:</b>  <code>{html_escape(order.vehicle_model or 'Nomalum')}</code>\n"
                f"👤 <b>Mijoz:</b>  <code>{html_escape(order.client_name)}</code>\n\n"
                f"🛠 <b>Bajariladigan xizmatlar:</b>\n{svcs}\n\n"
                f"💵 <b>Hisoblangan summa:</b>  <code>{format_amount(order.total_amount)}</code>\n"
                f"📊 <b>Joriy holat:</b>  {s_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔔 <i>Avtomobilingiz ishonchli qo'llarda! Barcha ishlar yakunlanganida botimiz orqali sizni darhol xabardor qilamiz.</i>"
            )
        await state.clear()
        await msg.answer(ans, reply_markup=ReplyKeyboardRemove())
        return

    await msg.answer("Iltimos, mijoz bo'lsangiz 5 xonali harf-raqamli, usta bo'lsangiz 6 xonali kodingizni kiriting.")


# ═══════════════════════════════════════════════════════════════════════════
#  ISHLAR RO'YXATI
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == "📋 Mening ishlarim")
async def master_jobs(msg: Message) -> None:
    master = await get_linked_master(msg.from_user.id)
    if not master:
        await msg.answer("❌ Siz usta sifatida ro'yxatdan o'tmagansiz.")
        return
    if not master.group_id:
        await msg.answer("⚠️ Siz hali guruhga qo'shilmagansiz. Admin bilan bog'laning.")
        return

    async with session_scope() as s:
        jobs = await ActiveJobRepository(s).get_active_jobs_for_group(master.group_id)
        items = []
        for j in jobs:
            o = await s.get(Order, j.order_id)
            if o:
                items.append((j, o))

    if not items:
        await msg.answer("🎉 Hozirda tayinlangan ish yo'q.")
        return
    await msg.answer(f"📋 Ishlar ({len(items)}):", reply_markup=master_jobs_kb(items))


@router.message(F.text == "🔄 Yangilash")
async def master_refresh(msg: Message) -> None:
    master = await get_linked_master(msg.from_user.id)
    if master:
        await show_master_home(msg)
        return
    # Agar usta emas — bosh menuga
    from handlers.common import show_main_menu
    await show_main_menu(msg, msg.from_user.id)


@router.callback_query(F.data == "mj:list")
async def master_jobs_cb(cb: CallbackQuery) -> None:
    await cb.answer()
    master = await get_linked_master(cb.from_user.id)
    if not master or not master.group_id:
        return
    async with session_scope() as s:
        jobs = await ActiveJobRepository(s).get_active_jobs_for_group(master.group_id)
        items = [(j, await s.get(Order, j.order_id)) for j in jobs]
        items = [(j, o) for j, o in items if o]
    if not items:
        await safe_edit(cb, "🎉 Ish yo'q.", None)
        return
    await safe_edit(cb, f"📋 Ishlar ({len(items)}):", master_jobs_kb(items))


# ═══════════════════════════════════════════════════════════════════════════
#  ISH TAFSILOTLARI
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mj:v:"))
async def master_job_view(cb: CallbackQuery) -> None:
    await cb.answer()
    jid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        job = await ActiveJobRepository(s).get_job_by_id(jid)
        order = await s.get(Order, job.order_id) if job else None
    if not job or not order:
        await cb.message.answer("❌ Topilmadi.")
        return

    svcs = "\n".join(f"• {x}" for x in order.service_names_list) or "—"
    started = job.started_at is not None
    time_info = ""
    if job.started_at:
        elapsed = datetime.utcnow() - job.started_at
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        mins = remainder // 60
        time_info = f"\n\n⏱ <b>Ish vaqti:</b> {hours} soat {mins} daqiqa"

    text = (
        f"<b>📋 Ish №{order.id}</b>\n\n"
        f"<b>Mijoz:</b> {html_escape(order.client_name)}\n"
        f"<b>Telefon:</b> {html_escape(order.client_phone)}\n"
        f"<b>Model:</b> {html_escape(order.vehicle_model or '—')}\n"
        f"<b>VIN:</b> {html_escape(order.vin or '—')}\n"
        f"<b>Balandlik:</b> {html_escape(order.van_height or '—')}\n\n"
        f"<b>Xizmatlar:</b>\n{svcs}"
        f"{time_info}"
    )
    if started:
        text += "\n\n🟢 <b>Ish boshlangan</b>"
    await safe_edit(cb, text, master_job_detail_kb(jid, started))


# ═══════════════════════════════════════════════════════════════════════════
#  ISH BOSHLASH (vaqt hisobi)
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mj:start:"))
async def master_start_job(cb: CallbackQuery) -> None:
    await cb.answer("Ish boshlandi!")
    jid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        await ActiveJobRepository(s).start_job(jid)
        job = await ActiveJobRepository(s).get_job_by_id(jid)
        order = await s.get(Order, job.order_id) if job else None

    if not job or not order:
        return

    svcs = "\n".join(f"• {x}" for x in order.service_names_list) or "—"
    text = (
        f"<b>📋 Ish №{order.id}</b>\n\n"
        f"<b>Mijoz:</b> {html_escape(order.client_name)}\n"
        f"<b>Model:</b> {html_escape(order.vehicle_model or '—')}\n\n"
        f"<b>Xizmatlar:</b>\n{svcs}\n\n"
        f"🟢 <b>Ish boshlandi!</b> ⏱ Vaqt hisoblanmoqda..."
    )
    await safe_edit(cb, text, master_job_detail_kb(jid, True))


# ═══════════════════════════════════════════════════════════════════════════
#  ISH YAKUNLASH — video so'rash
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mj:done:"))
async def master_job_done(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    jid = int(cb.data.split(":")[-1])
    await state.update_data(completing_job_id=jid)
    await state.set_state(MasterStates.waiting_completion_video)
    await cb.message.answer(
        "📹 Mashinaning holatini video qilib yuboring.\nBekor qilish: /cancel",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("cancel"), StateFilter(MasterStates.waiting_completion_video))
async def master_cancel_video(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await show_master_home(msg)


@router.message(MasterStates.waiting_completion_video, F.video | F.video_note)
async def master_recv_video(msg: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    jid = data.get("completing_job_id")
    if not jid:
        await state.clear()
        return

    vid = msg.video.file_id if msg.video else msg.video_note.file_id
    is_video = msg.video is not None
    master = await get_linked_master(msg.from_user.id)
    if not master:
        await state.clear()
        await msg.answer("❌ Usta topilmadi.")
        return

    async with session_scope() as s:
        jr = ActiveJobRepository(s)
        job = await jr.complete_job(jid, master.id, vid)
        order = await s.get(Order, job.order_id) if job else None

    await state.clear()

    # Ish vaqtini ko'rsatish
    time_info = ""
    if job and job.started_at and job.completed_at:
        elapsed = job.completed_at - job.started_at
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        mins = remainder // 60
        time_info = f"\n⏱ Ish vaqti: {hours} soat {mins} daqiqa"

    await msg.answer(f"✅ Xizmat bajarildi!{time_info}")
    await show_master_home(msg)

    # Hisobot chatga yuborish
    if order:
        # --- GOOGLE SHEETS COMPLETION SCRIPT ---
        try:
            import asyncio
            from google_sheets import complete_order_in_sheet
            from datetime import datetime
            
            c_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            asyncio.create_task(asyncio.to_thread(complete_order_in_sheet, str(order.id), c_time))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Google Sheets tugallashda xatolik: {e}")
        # --------------------------------------

        await send_completion_report(bot, order, master, vid, is_video, COMPLETION_REPORT_CHAT_ID)

        # Mijozga bildirishnoma
        if order.client_telegram_id:
            from utils import format_amount
            client_msg = (
                f"🎉 <b>Hurmatli {html_escape(order.client_name)}!</b>\n\n"
                f"Sizning <b>{html_escape(order.vehicle_model or 'mashina')}</b>ngiz mashinasi bo'yicha ta'mirlash ishlari to'liq yakunlandi!\n\n"
                f"💰 <b>Umumiy summa:</b> {format_amount(order.total_amount)}\n\n"
                f"Kelib olib ketishingiz mumkin. Lider Avtotex 555 markazini tanlaganingiz uchun rahmat oq yo'l!"
            )
            try:
                await bot.send_message(order.client_telegram_id, client_msg)
            except Exception:
                pass


@router.message(MasterStates.waiting_completion_video)
async def master_video_invalid(msg: Message) -> None:
    await msg.answer("📹 Iltimos, video yoki dumaloq video yuboring.")
