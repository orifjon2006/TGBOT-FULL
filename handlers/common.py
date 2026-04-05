"""Umumiy handlerlar — /start, cancel, refresh, registration, fallback."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_EXTRA,
    BTN_REFRESH,
    BTN_REGISTER_SUBADMIN,
    MAIN_ADMIN_TELEGRAM_ID,
)
from database import (
    MasterRepository,
    User,
    UserRepository,
    UserRole,
    session_scope,
)
from keyboards import (
    back_cancel_kb,
    extra_menu_kb,
    guest_kb,
    main_menu_kb,
    master_home_kb,
)
from states import MasterStates, RegistrationStates
from utils import build_display_name, normalize_phone, html_escape, format_amount

router = Router(name="common")


# ═══════════════════════════════════════════════════════════════════════════
#  Yordamchi funksiyalar
# ═══════════════════════════════════════════════════════════════════════════

async def get_db_user(telegram_id: int) -> User | None:
    async with session_scope() as s:
        return await UserRepository(s).get_by_telegram_id(telegram_id)


async def is_main_admin(telegram_id: int) -> bool:
    user = await get_db_user(telegram_id)
    return bool(user and user.role == UserRole.ADMIN and user.is_active)


async def is_admin_like(telegram_id: int) -> bool:
    user = await get_db_user(telegram_id)
    return bool(user and user.role in {UserRole.ADMIN, UserRole.SUBADMIN} and user.is_active)


async def bootstrap_main_admin(from_user) -> None:
    if MAIN_ADMIN_TELEGRAM_ID <= 0 or from_user.id != MAIN_ADMIN_TELEGRAM_ID:
        return
    async with session_scope() as session:
        repo = UserRepository(session)
        db_user = await repo.get_by_telegram_id(from_user.id)
        if db_user is None:
            await repo.create_user(
                telegram_id=from_user.id,
                full_name=build_display_name(from_user),
                phone_number=None,
                role=UserRole.ADMIN,
            )
        else:
            db_user.role = UserRole.ADMIN
            db_user.is_active = True
            db_user.full_name = build_display_name(from_user)
            await session.flush()


async def show_main_menu(message: Message, telegram_id: int) -> None:
    user = await get_db_user(telegram_id)
    if user and user.role in {UserRole.ADMIN, UserRole.SUBADMIN} and user.is_active:
        await message.answer(
            "🏠 <b>Bosh menu</b>\nKerakli amalni tanlang:",
            reply_markup=main_menu_kb(is_main_admin=user.role == UserRole.ADMIN),
        )
        return
    if user and user.role == UserRole.PENDING_SUBADMIN:
        await message.answer(
            "⏳ So'rovingiz yuborilgan. Asosiy admin tasdiqlashini kuting.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await message.answer(
        "Shaxsingiz tasdiqlanmagan. Agar usta bo'lsangiz kodingizni jo'nating.",
        reply_markup=ReplyKeyboardRemove(),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await bootstrap_main_admin(message.from_user)

    # Agar usta sifatida ulangan bo'lsa
    async with session_scope() as s:
        master = await MasterRepository(s).get_by_telegram_id(message.from_user.id)
    if master:
        await message.answer(
            f"👋 Xush kelibsiz, <b>{master.full_name}</b>!\nUsta paneli.",
            reply_markup=master_home_kb(),
        )
        return

    # Admin yoki oddiy user
    db_user = await get_db_user(message.from_user.id)
    if db_user and db_user.role in {UserRole.ADMIN, UserRole.SUBADMIN} and db_user.is_active:
        await show_main_menu(message, message.from_user.id)
        return

    # Mijozning aktiv buyurtmalari bormi?
    async with session_scope() as s:
        from database import Order
        from sqlalchemy import select
        res = await s.execute(
            select(Order)
            .where(Order.client_telegram_id == message.from_user.id)
            .where(Order.status == "active")
            .order_by(Order.created_at.desc())
        )
        orders = res.scalars().all()

    if orders:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        for order in orders:
            status_map = {
                "active": "🛠 Bajarilmoqda",
                "completed": "✅ Yakunlangan",
                "cancelled": "❌ Bekor qilingan",
                "closed": "📦 Yopilgan"
            }
            s_text = status_map.get(order.status, order.status or "🛠 Bajarilmoqda")
            svcs = "\\n".join(f"🔸 {x}" for x in order.service_names_list) or "—"
            
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
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"client:refresh:{order.id}")],
                [InlineKeyboardButton(text="🔎 Boshqa kod kiritish", callback_data="client:new_code")]
            ])
            await message.answer(ans, reply_markup=kb)
        return

    # User
    welcome_text = (
        "🚘 <b>Xush kelibsiz!</b>\n"
        "<i>«Lider Avto 555» sizning ishonchli avto xizmatingiz.</i>\n\n"
        "✨ <b>Sizning avtomobilingiz qanday holatda ekanligini bilmoqchimisiz?</b>\n"
        "Buning uchun adminga murojaat qilib olingan <b>5 xonali maxsus mijoz kodi</b>ni kiriting.\n\n"
        "👨‍🔧 <i>Agar siz usta bo'lsangiz, o'zingizning <b>6 xonali usta kodi</b>ngizni kiriting.</i>\n\n"
        "👇 Iltimos, kodni joriy chatga yozib yuboring:"
    )
    await message.answer(
        welcome_text,
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(MasterStates.waiting_access_code)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await bootstrap_main_admin(message.from_user)

    db_user = await get_db_user(message.from_user.id)
    if db_user and db_user.role in {UserRole.ADMIN, UserRole.SUBADMIN} and db_user.is_active:
        await show_main_menu(message, message.from_user.id)
        return
    if db_user and db_user.role == UserRole.PENDING_SUBADMIN:
        await message.answer("⏳ So'rovingiz yuborilgan. Asosiy admin tasdiqlashini kuting.", reply_markup=ReplyKeyboardRemove())
        return

    await start_subadmin_registration(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  Yangilash
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
#  YANGILASH VA MIJOZ CALLBACK'LARI
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("client:refresh:"))
async def client_refresh_order(cb: CallbackQuery) -> None:
    order_id = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        from database import Order
        order = await s.get(Order, order_id)
        if not order:
            await cb.answer("Topilmadi", show_alert=True)
            return
        
        status_map = {
            "active": "🛠 Bajarilmoqda",
            "completed": "✅ Yakunlangan",
            "cancelled": "❌ Bekor qilingan",
            "closed": "📦 Yopilgan"
        }
        s_text = status_map.get(order.status, order.status or "🛠 Bajarilmoqda")
        svcs = "\\n".join(f"🔸 {x}" for x in order.service_names_list) or "—"
        
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
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"client:refresh:{order.id}")],
            [InlineKeyboardButton(text="🔎 Boshqa kod kiritish", callback_data="client:new_code")]
        ])
        
        try:
            await cb.message.edit_text(ans, reply_markup=kb)
            await cb.answer("Yangilandi")
        except Exception:
            await cb.answer("O'zgarish yo'q")


@router.callback_query(F.data == "client:new_code")
async def client_new_code(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    text = (
        "🔎 <b>Yangi avtomobilni tekshirish</b>\n\n"
        "Iltimos, yangi <b>5 xonali mijoz kodi</b>ni kiriting.\n"
        "<i>Yoki 6 xonali usta kodingiz bo'lsa, uni ham kiritishingiz mumkin.</i>"
    )
    await cb.message.answer(
        text,
        reply_markup=ReplyKeyboardRemove()
    )
    from states import MasterStates
    await state.set_state(MasterStates.waiting_access_code)


@router.message(F.text == BTN_REFRESH)
async def refresh_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await bootstrap_main_admin(message.from_user)
    await show_main_menu(message, message.from_user.id)


# ═══════════════════════════════════════════════════════════════════════════
#  Bekor qilish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(StateFilter("*"), F.text == BTN_CANCEL)
async def cancel_any_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await show_main_menu(message, message.from_user.id)


@router.callback_query(F.data == "global:cancel")
async def cancel_any_flow_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Bekor qilindi")
    await state.clear()
    await callback.message.answer("❌ Amal bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await show_main_menu(callback.message, callback.from_user.id)


# ═══════════════════════════════════════════════════════════════════════════
#  Qo'shimcha menu
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_EXTRA)
async def show_extra_menu(message: Message, state: FSMContext) -> None:
    if not await is_admin_like(message.from_user.id):
        await message.answer("Bu bo'lim faqat adminlar uchun.")
        return
    await state.clear()
    _is_main = await is_main_admin(message.from_user.id)
    await message.answer(
        "⚙️ <b>Qo'shimcha</b>\nBoshqaruv va sozlamalar:",
        reply_markup=extra_menu_kb(_is_main),
    )


@router.message(F.text == BTN_BACK, StateFilter(None))
async def back_to_main_menu(message: Message, state: FSMContext) -> None:
    """Qo'shimcha menuda Ortga bosilganda bosh menuga qaytish."""
    await state.clear()
    await show_main_menu(message, message.from_user.id)


# ═══════════════════════════════════════════════════════════════════════════
#  Subadmin ro'yxatdan o'tish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_REGISTER_SUBADMIN)
async def start_subadmin_registration(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RegistrationStates.waiting_full_name)
    await message.answer("To'liq ismingizni kiriting:", reply_markup=back_cancel_kb())


@router.message(RegistrationStates.waiting_full_name)
async def process_reg_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_BACK:
        await state.clear()
        await show_main_menu(message, message.from_user.id)
        return
    if len(text) < 3:
        await message.answer("Iltimos, to'liq ismni to'g'ri kiriting.")
        return
    await state.update_data(reg_full_name=text)
    await state.set_state(RegistrationStates.waiting_phone)
    await message.answer("Telefon raqamingizni kiriting:", reply_markup=back_cancel_kb())


@router.message(RegistrationStates.waiting_phone)
async def process_reg_phone(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_full_name)
        await message.answer("To'liq ismingizni qayta kiriting:", reply_markup=back_cancel_kb())
        return

    try:
        phone = normalize_phone(message.text or "")
    except ValueError as e:
        await message.answer(str(e))
        return

    data = await state.get_data()
    full_name = data.get("reg_full_name")

    async with session_scope() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_telegram_id(message.from_user.id)
        if existing is None:
            await repo.create_user(
                telegram_id=message.from_user.id,
                full_name=full_name,
                phone_number=phone,
                role=UserRole.PENDING_SUBADMIN,
            )
        else:
            existing.full_name = full_name
            existing.phone_number = phone
            existing.role = UserRole.PENDING_SUBADMIN
            existing.is_active = True
            await session.flush()

    await state.clear()
    await message.answer(
        "✅ So'rovingiz yuborildi. Asosiy admin tasdiqlashini kuting.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(F.text == BTN_BACK, StateFilter(RegistrationStates.waiting_full_name))
async def back_from_reg_name(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_main_menu(message, message.from_user.id)
