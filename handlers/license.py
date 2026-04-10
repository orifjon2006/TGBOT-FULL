from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states import LicenseStates, LicenseSearchStates
from keyboards import back_cancel_kb, main_menu_kb
from database import session_scope, LicenseRepository, Order
from config import BTN_LICENSE_ADD, BTN_LICENSE_CHECK, BTN_BACK
from handlers.common import is_admin_like, is_main_admin
from google_sheets import append_license_to_sheet
import asyncio

router = Router()

def get_issue_dates() -> tuple[str, str]:
    now = datetime.now()
    applied = now.strftime("%Y-%m-%d")
    issued = (now + timedelta(days=10)).strftime("%Y-%m-%d")
    return applied, issued


def license_info_text(lic, order_num: str = None) -> str:
    text = (
        f"📜 <b>LITSENZIYA MA'LUMOTI</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔢 <b>VIN Kod:</b> <code>{lic.vin_code}</code>\n"
        f"👤 <b>Mijoz:</b> {lic.client_name or '—'}\n"
        f"📞 <b>Telefon:</b> {lic.client_phone or '—'}\n"
        f"📩 <b>Ariza raqami:</b> <code>{lic.application_number or '—'}</code>\n"
        f"📥 <b>Topshirilgan:</b> {lic.applied_date}\n"
        f"📤 <b>Tayyor bo'ladi:</b> <b>{lic.issuance_date}</b>"
    )
    if lic.order_id or order_num:
        on = order_num or lic.order_id
        text += f"\n🔖 <b>Zakaz №:</b> {on}"
    return text


# ═══════════════════════════════════════════════════════════════════════════
#  BUYURTMAGA LITSENZIYA BOG'LASH (Callback)
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("lic:view:"))
async def cb_view_license(cb: CallbackQuery, state: FSMContext):
    """Buyurtma tafsilotidan litsenziyani ko'rish."""
    await cb.answer()
    val = cb.data.split("lic:view:", 1)[1]
    
    async with session_scope() as s:
        repo = LicenseRepository(s)
        lic = None
        oid = None
        
        if val.startswith("order_"):
            oid = int(val.replace("order_", ""))
            lic = await repo.get_by_order_id(oid)
        else:
            lic = await repo.get_by_vin(val)
            if not lic:
                # Agar VIN topilmasa, balki bu VIN qaysidir orderga tegishlidir?
                from sqlalchemy import select
                res = await s.execute(select(Order).where(Order.vin == val))
                order = res.scalar_one_or_none()
                if order:
                    oid = order.id

    if lic:
        await cb.message.answer(license_info_text(lic))
    else:
        is_adm = await is_admin_like(cb.from_user.id)
        if is_adm:
            builder = InlineKeyboardBuilder()
            if oid:
                builder.button(text="📝 Litsenziya qo'shish", callback_data=f"lic:create:{oid}")
            else:
                builder.button(text="📝 Litsenziya qo'shish", callback_data=f"lic:create_vin:{val}")
            
            await cb.message.answer(
                f"⚠️ Litsenziya topilmadi.\nYangi litsenziya qo'shishni xohlaysizmi?",
                reply_markup=builder.as_markup()
            )
        else:
            await cb.message.answer(f"❌ Litsenziya topilmadi.")


@router.callback_query(F.data.startswith("lic:create_vin:"))
async def cb_create_from_vin(cb: CallbackQuery, state: FSMContext):
    """Faqat VIN orqali yaratish (order_id yo'q bo'lishi mumkin)."""
    await cb.answer()
    vin = cb.data.split("lic:create_vin:", 1)[1]
    await state.clear()
    await state.update_data(vin=vin)
    await state.set_state(LicenseStates.waiting_client_name)
    await cb.message.answer(f"📝 <b>{vin}</b> uchun litsenziya.\n👤 Mijoz ismini kiriting:", reply_markup=back_cancel_kb())


@router.callback_query(F.data.startswith("lic:create:"))
async def cb_create_license_from_order(cb: CallbackQuery, state: FSMContext):
    """Buyurtmadan TO'LIQ pre-fill qilingan holda yaratish."""
    await cb.answer()
    oid = int(cb.data.split("lic:create:", 1)[1])
    
    async with session_scope() as s:
        order = await s.get(Order, oid)
    
    if not order:
        await cb.message.answer("❌ Buyurtma topilmadi.")
        return

    await state.clear()
    await state.update_data(
        order_id=oid,
        vin=order.vin or "",
        name=order.client_name,
        phone=order.client_phone
    )
    
    # Agar VIN bo'lsa, ismdan boshlaymiz, aks holda VINdan
    if order.vin:
        await state.set_state(LicenseStates.waiting_client_name)
        await cb.message.answer(
            f"📝 Zakaz №{oid} asosida litsenziya.\n"
            f"🔢 <b>VIN:</b> {order.vin}\n\n"
            f"👤 Mijoz ismi: <b>{order.client_name}</b>\n"
            f"Ismni o'zgartirish uchun yozing yoki tasdiqlash uchun ismni qayta yuboring:",
            reply_markup=back_cancel_kb()
        )
    else:
        await state.set_state(LicenseStates.waiting_vin)
        await cb.message.answer(
            f"📝 Zakaz №{oid} uchun litsenziya.\n\n"
            f"🔢 Avtomobil VIN kodini kiriting:",
            reply_markup=back_cancel_kb()
        )


# ═══════════════════════════════════════════════════════════════════════════
#  LITSENZIYA QO'SHISH — Admin FSM
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_LICENSE_ADD)
async def start_add_license(message: Message, state: FSMContext):
    if not await is_admin_like(message.from_user.id):
        await message.answer("❌ Bu bo'lim faqat adminlar uchun.")
        return
    await state.clear()
    await state.set_state(LicenseStates.waiting_vin)
    await message.answer("📝 Litsenziya qo'shish.\n\n🔢 Avtomobil VIN kodini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_vin, F.text == BTN_BACK)
async def back_from_vin(message: Message, state: FSMContext):
    await state.clear()
    from handlers.common import show_main_menu
    await show_main_menu(message, message.from_user.id)


@router.message(LicenseStates.waiting_vin)
async def process_vin(message: Message, state: FSMContext):
    vin = (message.text or "").strip().upper()
    if len(vin) < 3:
        await message.answer("❌ VIN kod juda qisqa, qayta kiriting.")
        return

    async with session_scope() as s:
        repo = LicenseRepository(s)
        existing = await repo.get_by_vin(vin)
        if existing:
            await message.answer(f"⚠️ Bu VIN uchun litsenziya allaqachon mavjud!\n\n" + license_info_text(existing))
            return

    await state.update_data(vin=vin)
    data = await state.get_data()
    
    # Agar pre-fill bo'lsa va ism bo'lsa, telefonni so'raymiz
    if data.get("name"):
        await state.set_state(LicenseStates.waiting_client_name)
        await message.answer(f"👤 Mijoz ismi: <b>{data['name']}</b>\nTasdiqlash uchun ismni yuboring yoki o'zgartiring:", reply_markup=back_cancel_kb())
    else:
        await state.set_state(LicenseStates.waiting_client_name)
        await message.answer("👤 Mijoz ismini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_client_name, F.text == BTN_BACK)
async def back_from_name(message: Message, state: FSMContext):
    await state.set_state(LicenseStates.waiting_vin)
    await message.answer("🔢 Avtomobil VIN kodini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_client_name)
async def process_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Ism juda qisqa.")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    
    if data.get("phone"):
        await state.set_state(LicenseStates.waiting_client_phone)
        await message.answer(f"📞 Telefon raqami: <b>{data['phone']}</b>\nTasdiqlash uchun raqamni yuboring yoki o'zgartiring:", reply_markup=back_cancel_kb())
    else:
        await state.set_state(LicenseStates.waiting_client_phone)
        await message.answer("📞 Mijoz telefon raqamini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_client_phone, F.text == BTN_BACK)
async def back_from_phone(message: Message, state: FSMContext):
    await state.set_state(LicenseStates.waiting_client_name)
    await message.answer("👤 Mijoz ismini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_client_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    await state.update_data(phone=phone)
    await state.set_state(LicenseStates.waiting_application_number)
    await message.answer("📩 Ariza raqamini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_application_number, F.text == BTN_BACK)
async def back_from_app_number(message: Message, state: FSMContext):
    await state.set_state(LicenseStates.waiting_client_phone)
    data = await state.get_data()
    phone = data.get("phone", "")
    if phone:
        await message.answer(f"📞 Mijoz telefon raqamini kiriting/tasdiqlang (eski qiymat: {phone}):", reply_markup=back_cancel_kb())
    else:
        await message.answer("📞 Mijoz telefon raqamini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseStates.waiting_application_number)
async def process_application_number(message: Message, state: FSMContext):
    app_num = (message.text or "").strip()
    data = await state.get_data()
    vin = data.get("vin")
    name = data.get("name")
    phone = data.get("phone")
    order_id = data.get("order_id")

    applied, issuance = get_issue_dates()

    async with session_scope() as s:
        repo = LicenseRepository(s)
        lic = await repo.create(
            vin_code=vin,
            applied_date=applied,
            issuance_date=issuance,
            client_name=name,
            client_phone=phone,
            order_id=order_id,
            application_number=app_num
        )

    # Google Sheets: [VIN, Name, Phone, Applied, Issued, Order#, ApplicationNum]
    sheet_data = [vin, name, phone, applied, issuance, str(order_id or "—"), app_num]
    asyncio.create_task(asyncio.to_thread(append_license_to_sheet, sheet_data))

    _is_main = await is_main_admin(message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ <b>Litsenziya ro'yxatga olindi!</b>\n\n" + license_info_text(lic, order_num=str(order_id if order_id else "")),
        reply_markup=main_menu_kb(_is_main)
    )


# ═══════════════════════════════════════════════════════════════════════════
#  LITSENZIYA QIDIRISH
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_LICENSE_CHECK)
async def start_check_license(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(LicenseSearchStates.waiting_search_vin)
    await message.answer("🔎 Litsenziyani tekshirish.\n\nAvtomobil VIN kodini (yoki uning oxirgi qismini) yoki Ariza raqamini kiriting:", reply_markup=back_cancel_kb())


@router.message(LicenseSearchStates.waiting_search_vin, F.text == BTN_BACK)
async def back_from_search(message: Message, state: FSMContext):
    await state.clear()
    from handlers.common import show_main_menu
    await show_main_menu(message, message.from_user.id)


@router.message(LicenseSearchStates.waiting_search_vin)
async def process_search_vin(message: Message, state: FSMContext):
    search_val = (message.text or "").strip().upper()
    async with session_scope() as s:
        repo = LicenseRepository(s)
        # Avval to'liq VIN bo'yicha
        results = await repo.search_by_vin_partial(search_val)

    _is_main = await is_main_admin(message.from_user.id)
    
    if not results:
        is_adm = await is_admin_like(message.from_user.id)
        if is_adm and len(search_val) >= 7:
            builder = InlineKeyboardBuilder()
            builder.button(text="📝 Yangi litsenziya qo'shish", callback_data=f"lic:create_vin:{search_val}")
            await message.answer(f"❌ <b>{search_val}</b> bo'yicha hech narsa topilmadi.\n(Xohlasangiz buni VIN deb qabul qilib, yangi litsenziya qo'shishingiz mumkin)", reply_markup=builder.as_markup())
        else:
            await message.answer("❌ Hech narsa topilmadi. Qayta urinib ko'ring.", reply_markup=main_menu_kb(_is_main))
        return

    await state.clear()
    if len(results) == 1:
        await message.answer(license_info_text(results[0]), reply_markup=main_menu_kb(_is_main))
    else:
        # Bir nechta topilsa ro'yxat chiqaramiz
        text = f"🔎 <b>{search_val}</b> bo'yicha {len(results)} ta natija topildi:\n\n"
        for i, l in enumerate(results, 1):
            text += f"{i}. <code>{l.vin_code}</code> — {l.client_name or '—'} ({l.issuance_date})\n"
        await message.answer(text, reply_markup=main_menu_kb(_is_main))


# Wildcard filter
class WildcardVINFilter(Filter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        if await state.get_state() is not None: return False
        val = (message.text or "").strip()
        if len(val) >= 5 and val.isalnum() and not val.startswith("/"): return True
        return False

@router.message(WildcardVINFilter())
async def wildcard_vin_search(message: Message, state: FSMContext):
    search_val = (message.text or "").strip().upper()
    async with session_scope() as s:
        repo = LicenseRepository(s)
        results = await repo.search_by_vin_partial(search_val)
    
    if results:
        if len(results) == 1:
            await message.answer(license_info_text(results[0]))
        else:
            text = f"🔎 Topilgan litsenziyalar:\n"
            for l in results[:5]: # Maksimum 5 ta
                text += f"• <code>{l.vin_code}</code> — {l.issuance_date}\n"
            await message.answer(text)
