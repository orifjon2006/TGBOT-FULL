"""Qidirish — kengaytirilgan: telefon, ism, model, VIN bo'yicha."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from config import BTN_BACK, BTN_SEARCH_CLIENT
from database import OrderRepository, session_scope
from keyboards import back_cancel_kb, search_result_kb, search_type_kb
from services import build_search_excel
from states import SearchStates
from utils import format_amount, html_escape, normalize_phone, split_long_text

router = Router(name="search")


async def safe_edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


# ═══════════════════════════════════════════════════════════════════════════
#  Qidiruvni boshlash
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_SEARCH_CLIENT)
async def start_search(message: Message, state: FSMContext) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        await message.answer("Bu bo'lim faqat adminlar uchun.")
        return
    await state.clear()
    await message.answer(
        "🔎 Qidiruv turini tanlang:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Qanday qidirmoqchisiz?",
        reply_markup=search_type_kb(),
    )


@router.callback_query(F.data.startswith("srch:type:"))
async def search_type_selected(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    search_type = cb.data.split(":")[-1]
    await state.clear()
    await state.update_data(search_type=search_type)
    await state.set_state(SearchStates.waiting_query)

    labels = {
        "phone": "📞 Telefon raqamni kiriting:",
        "name": "👤 Mijoz ismini kiriting:",
        "model": "🚐 Model nomini kiriting:",
        "vin": "🔢 VIN kodini kiriting:",
    }
    await cb.message.answer(labels.get(search_type, "Qidiruv so'rovini kiriting:"), reply_markup=back_cancel_kb())


@router.callback_query(F.data == "search:new")
async def search_new(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await cb.message.answer("🔎 Qidiruv turini tanlang:", reply_markup=search_type_kb())


# ═══════════════════════════════════════════════════════════════════════════
#  So'rov kiritish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(SearchStates.waiting_query, F.text == BTN_BACK)
async def search_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    from handlers.common import show_main_menu
    await show_main_menu(message, message.from_user.id)


@router.message(SearchStates.waiting_query)
async def process_search_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("❌ So'rov bo'sh.")
        return

    data = await state.get_data()
    search_type = data.get("search_type", "phone")

    # Telefon qidiruv uchun normalizatsiya
    if search_type == "phone":
        try:
            query = normalize_phone(query)
        except ValueError as e:
            await message.answer(str(e))
            return

    async with session_scope() as s:
        orders = await OrderRepository(s).search_orders(query, search_type)

    if not orders:
        await message.answer(
            "❌ Bu so'rov bo'yicha hech narsa topilmadi.\nBoshqa so'rov kiriting yoki bekor qiling.",
            reply_markup=back_cancel_kb(),
        )
        return

    await state.update_data(search_query=query)
    await state.set_state(SearchStates.waiting_output_format)

    await message.answer(
        f"✅ {len(orders)} ta buyurtma topildi.\nNatijani qaysi ko'rinishda olishni xohlaysiz?",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Variantni tanlang:", reply_markup=search_result_kb())


# ═══════════════════════════════════════════════════════════════════════════
#  Natijani ko'rsatish
# ═══════════════════════════════════════════════════════════════════════════

def build_search_text(query: str, orders: list) -> str:
    lines = [
        "<b>🔎 Qidiruv natijasi</b>",
        "",
        f"<b>So'rov:</b> {html_escape(query)}",
        f"<b>Topilgan buyurtmalar:</b> {len(orders)} ta",
    ]
    for order in orders:
        svcs = ", ".join(order.service_names_list) or "—"
        masters = ", ".join(order.master_names_list) or "—"
        status_text = {"active": "🟢 Aktiv", "completed": "✅ Bajarilgan", "cancelled": "🔴 Bekor"}.get(
            order.status or "active", "—"
        )
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━",
            f"🔖 <b>Zakaz №{order.order_number}</b>  {status_text}",
            f"📅 <b>Sana:</b>  {order.confirmed_at.strftime('%d.%m.%Y') if order.confirmed_at else '—'}",
            f"👤 <b>Mijoz:</b>  <code>{html_escape(order.client_name)}</code>",
            f"📞 <b>Telefon:</b>  <code>{html_escape(order.client_phone)}</code>",
            f"🚘 <b>Model:</b>  <code>{html_escape(order.vehicle_model_name_snapshot)}</code>",
            f"🔢 <b>VIN:</b>  <code>{html_escape(order.vin_code or '—')}</code>",
            f"📏 <b>Balandlik:</b>  <code>{html_escape(order.van_height_name_snapshot)}</code>",
            "",
            f"🛠 <b>Xizmatlar:</b>\n🔸 {html_escape(svcs)}",
            "",
            f"💵 <b>Summa:</b>  <code>{format_amount(order.total_amount)}</code>",
            f"👥 <b>Ustalar:</b>  {html_escape(masters)}",
        ])
        if order.comment:
            lines.append(f"<b>Izoh:</b> {html_escape(order.comment)}")
    return "\n".join(lines)


@router.callback_query(F.data == "search:show_text")
async def search_show_text(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    data = await state.get_data()
    query = data.get("search_query")
    search_type = data.get("search_type", "phone")

    if not query:
        await cb.message.answer("❌ So'rov topilmadi. Qaytadan boshlang.")
        await state.clear()
        return

    async with session_scope() as s:
        orders = await OrderRepository(s).search_orders(query, search_type)

    if not orders:
        await cb.message.answer("❌ Buyurtma topilmadi.")
        return

    text = build_search_text(query, orders)
    for chunk in split_long_text(text, 3500):
        await cb.message.answer(chunk)

    await cb.message.answer("Excel faylni ham olish mumkin.", reply_markup=search_result_kb())


@router.callback_query(F.data == "search:show_excel")
async def search_show_excel(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer("Excel tayyorlanmoqda...")
    data = await state.get_data()
    query = data.get("search_query")
    search_type = data.get("search_type", "phone")

    if not query:
        await cb.message.answer("❌ So'rov topilmadi.")
        await state.clear()
        return

    async with session_scope() as s:
        orders = await OrderRepository(s).search_orders(query, search_type)

    if not orders:
        await cb.message.answer("❌ Buyurtma topilmadi.")
        return

    file_path = build_search_excel(query, orders)
    try:
        doc = FSInputFile(file_path)
        await cb.message.answer_document(
            document=doc,
            caption=f"📄 Qidiruv natijasi: {len(orders)} ta buyurtma",
        )
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass

    await cb.message.answer("Yana natija olish:", reply_markup=search_result_kb())


@router.message(SearchStates.waiting_output_format)
async def search_buttons_only(message: Message) -> None:
    await message.answer("ℹ️ Bu bosqichda tugmalar orqali tanlang.")
