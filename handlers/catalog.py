"""Katalog boshqarish — modellar, xizmatlar, balandliklar, ustalar."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from config import (
    BTN_BACK,
    BTN_CATALOGS,
    BTN_HEIGHTS,
    BTN_MASTERS,
    BTN_MODELS,
    BTN_SERVICES,
    CATALOG_NAMES,
)
from database import (
    Master,
    MasterRepository,
    ServiceCatalog,
    VanHeight,
    VanHeightRepository,
    VehicleModel,
    VehicleModelRepository,
    ServiceRepository,
    session_scope,
)
from keyboards import back_cancel_kb, catalog_item_kb, catalog_list_kb, catalog_menu_kb
from states import CatalogStates
from utils import html_escape, normalize_phone

router = Router(name="catalog")


# ═══════════════════════════════════════════════════════════════════════════
#  Yordamchi
# ═══════════════════════════════════════════════════════════════════════════

async def safe_edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


def get_repo(session, catalog_type: str):
    return {
        "models": VehicleModelRepository,
        "services": ServiceRepository,
        "heights": VanHeightRepository,
        "masters": MasterRepository,
    }[catalog_type](session)


def get_model(catalog_type: str):
    return {"models": VehicleModel, "services": ServiceCatalog, "heights": VanHeight, "masters": Master}[catalog_type]


async def list_items(session, catalog_type: str) -> list:
    return await get_repo(session, catalog_type).list_active()


async def get_item(session, catalog_type: str, item_id: int):
    return await session.get(get_model(catalog_type), item_id)


def item_title(item) -> str:
    return getattr(item, "name", None) or getattr(item, "label", None) or getattr(item, "full_name", None) or str(item.id)


def build_item_text(catalog_type: str, item) -> str:
    active = "ha" if item.is_active else "yo'q"
    text = (
        f"<b>{html_escape(CATALOG_NAMES[catalog_type])}</b>\n\n"
        f"<b>ID:</b> {item.id}\n"
        f"<b>Nomi:</b> {html_escape(item_title(item))}\n"
        f"<b>Faolligi:</b> {active}\n"
        f"<b>Tartib:</b> {item.sort_order}"
    )
    if catalog_type == "masters":
        text += f"\n<b>Telefon:</b> {html_escape(item.phone_number or '—')}"
        if hasattr(item, "access_code") and item.access_code:
            text += f"\n<b>Kirish kodi:</b> {item.access_code}"
    return text


# ═══════════════════════════════════════════════════════════════════════════
#  Katalog menu ochish
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_CATALOGS)
async def open_catalog_menu(message: Message) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return
    await message.answer("🗂 Kerakli katalogni tanlang:", reply_markup=catalog_menu_kb())


@router.message(F.text.in_([BTN_MODELS, BTN_SERVICES, BTN_HEIGHTS, BTN_MASTERS]))
async def open_catalog_list(message: Message, state: FSMContext) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return

    mapping = {BTN_MODELS: "models", BTN_SERVICES: "services", BTN_HEIGHTS: "heights", BTN_MASTERS: "masters"}
    ct = mapping[message.text]
    await state.clear()
    await state.update_data(catalog_type=ct)

    async with session_scope() as s:
        items = await list_items(s, ct)
    await message.answer(f"{CATALOG_NAMES[ct]} ro'yxati:", reply_markup=catalog_list_kb(items, ct))


# ═══════════════════════════════════════════════════════════════════════════
#  Callback: list, item view
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "cat:menu")
async def cat_menu_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await cb.message.answer("🗂 Katalogni tanlang:", reply_markup=catalog_menu_kb())


@router.callback_query(F.data.startswith("cat:list:"))
async def cat_list_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    ct = cb.data.split(":")[-1]
    await state.clear()
    await state.update_data(catalog_type=ct)
    async with session_scope() as s:
        items = await list_items(s, ct)
    await safe_edit(cb, f"{CATALOG_NAMES[ct]} ro'yxati:", catalog_list_kb(items, ct))


@router.callback_query(F.data.startswith("cat:item:"))
async def cat_item_view(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    _, _, ct, iid = cb.data.split(":")
    iid = int(iid)
    async with session_scope() as s:
        item = await get_item(s, ct, iid)
    if not item:
        await cb.message.answer("❌ Element topilmadi.")
        return
    await state.clear()
    await state.update_data(catalog_type=ct, catalog_item_id=iid)
    await safe_edit(cb, build_item_text(ct, item), catalog_item_kb(ct, item.id, item.is_active))


# ═══════════════════════════════════════════════════════════════════════════
#  Qo'shish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cat:add:"))
async def cat_add_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    ct = cb.data.split(":")[-1]
    await state.clear()
    await state.update_data(catalog_type=ct, catalog_action="add")
    await state.set_state(CatalogStates.waiting_add_name)
    await cb.message.answer(f"{CATALOG_NAMES[ct]} uchun yangi nom kiriting:", reply_markup=back_cancel_kb())


@router.message(CatalogStates.waiting_add_name, F.text == BTN_BACK)
async def cat_add_back(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ct = data["catalog_type"]
    await state.clear()
    async with session_scope() as s:
        items = await list_items(s, ct)
    await message.answer(f"{CATALOG_NAMES[ct]} ro'yxati:", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"{CATALOG_NAMES[ct]} ro'yxati:", reply_markup=catalog_list_kb(items, ct))


@router.message(CatalogStates.waiting_add_name)
async def cat_add_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ct = data["catalog_type"]
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Nom juda qisqa.")
        return

    if ct == "masters":
        await state.update_data(new_master_name=name)
        await state.set_state(CatalogStates.waiting_add_master_phone)
        await message.answer("📞 Usta telefon raqamini kiriting (yoki - yuboring):", reply_markup=back_cancel_kb())
        return

    async with session_scope() as s:
        repo = get_repo(s, ct)
        await repo.add(name)
        items = await list_items(s, ct)

    await state.clear()
    await message.answer("✅ Muvaffaqiyatli qo'shildi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"{CATALOG_NAMES[ct]} ro'yxati:", reply_markup=catalog_list_kb(items, ct))


@router.message(CatalogStates.waiting_add_master_phone, F.text == BTN_BACK)
async def cat_add_master_phone_back(message: Message, state: FSMContext) -> None:
    await state.set_state(CatalogStates.waiting_add_name)
    await message.answer("Usta ismini qayta kiriting:", reply_markup=back_cancel_kb())


@router.message(CatalogStates.waiting_add_master_phone)
async def cat_add_master_phone(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    phone_text = (message.text or "").strip()
    try:
        phone = None if phone_text == "-" else normalize_phone(phone_text)
    except ValueError as e:
        await message.answer(str(e))
        return

    name = data.get("new_master_name")
    async with session_scope() as s:
        repo = MasterRepository(s)
        await repo.add(name, phone)
        items = await repo.list_active()

    await state.clear()
    await message.answer("✅ Usta qo'shildi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"{CATALOG_NAMES['masters']} ro'yxati:", reply_markup=catalog_list_kb(items, "masters"))


# ═══════════════════════════════════════════════════════════════════════════
#  Tahrirlash — nom, tartib, telefon
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cat:rename:"))
async def cat_rename_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    _, _, ct, iid = cb.data.split(":")
    await state.clear()
    await state.update_data(catalog_type=ct, catalog_item_id=int(iid))
    await state.set_state(CatalogStates.waiting_edit_name)
    await cb.message.answer("✏️ Yangi nomni kiriting:", reply_markup=back_cancel_kb())


@router.message(CatalogStates.waiting_edit_name, F.text == BTN_BACK)
async def cat_rename_back(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with session_scope() as s:
        item = await get_item(s, data["catalog_type"], data["catalog_item_id"])
    await state.clear()
    if item:
        await message.answer(
            build_item_text(data["catalog_type"], item),
            reply_markup=catalog_item_kb(data["catalog_type"], item.id, item.is_active),
        )


@router.message(CatalogStates.waiting_edit_name)
async def cat_rename_process(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Nom juda qisqa.")
        return
    data = await state.get_data()
    ct, iid = data["catalog_type"], data["catalog_item_id"]
    async with session_scope() as s:
        repo = get_repo(s, ct)
        if ct == "masters":
            await repo.update(iid, full_name=name)
        else:
            await repo.update(iid, name=name)
        item = await get_item(s, ct, iid)
    await state.clear()
    await message.answer("✅ Nom yangilandi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(build_item_text(ct, item), reply_markup=catalog_item_kb(ct, item.id, item.is_active))


@router.callback_query(F.data.startswith("cat:sort:"))
async def cat_sort_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    _, _, ct, iid = cb.data.split(":")
    await state.clear()
    await state.update_data(catalog_type=ct, catalog_item_id=int(iid))
    await state.set_state(CatalogStates.waiting_edit_sort_order)
    await cb.message.answer("↕️ Yangi tartib raqamini kiriting (masalan: 1):", reply_markup=back_cancel_kb())


@router.message(CatalogStates.waiting_edit_sort_order, F.text == BTN_BACK)
async def cat_sort_back(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with session_scope() as s:
        item = await get_item(s, data["catalog_type"], data["catalog_item_id"])
    await state.clear()
    if item:
        await message.answer(
            build_item_text(data["catalog_type"], item),
            reply_markup=catalog_item_kb(data["catalog_type"], item.id, item.is_active),
        )


@router.message(CatalogStates.waiting_edit_sort_order)
async def cat_sort_process(message: Message, state: FSMContext) -> None:
    try:
        order = int((message.text or "").strip())
    except ValueError:
        await message.answer("❌ Tartib raqami butun son bo'lishi kerak.")
        return
    data = await state.get_data()
    ct, iid = data["catalog_type"], data["catalog_item_id"]
    async with session_scope() as s:
        await get_repo(s, ct).update(iid, sort_order=order)
        item = await get_item(s, ct, iid)
    await state.clear()
    await message.answer("✅ Tartib yangilandi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(build_item_text(ct, item), reply_markup=catalog_item_kb(ct, item.id, item.is_active))


@router.callback_query(F.data.startswith("cat:phone:"))
async def cat_phone_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    _, _, ct, iid = cb.data.split(":")
    await state.clear()
    await state.update_data(catalog_type=ct, catalog_item_id=int(iid))
    await state.set_state(CatalogStates.waiting_edit_master_phone)
    await cb.message.answer("📞 Yangi telefon raqamini kiriting:", reply_markup=back_cancel_kb())


@router.message(CatalogStates.waiting_edit_master_phone, F.text == BTN_BACK)
async def cat_phone_back(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with session_scope() as s:
        item = await get_item(s, data["catalog_type"], data["catalog_item_id"])
    await state.clear()
    if item:
        await message.answer(
            build_item_text(data["catalog_type"], item),
            reply_markup=catalog_item_kb(data["catalog_type"], item.id, item.is_active),
        )


@router.message(CatalogStates.waiting_edit_master_phone)
async def cat_phone_process(message: Message, state: FSMContext) -> None:
    try:
        phone = normalize_phone(message.text or "")
    except ValueError as e:
        await message.answer(str(e))
        return
    data = await state.get_data()
    iid = data["catalog_item_id"]
    async with session_scope() as s:
        await MasterRepository(s).update(iid, phone_number=phone)
        item = await s.get(Master, iid)
    await state.clear()
    await message.answer("✅ Telefon yangilandi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(build_item_text("masters", item), reply_markup=catalog_item_kb("masters", item.id, item.is_active))


# ═══════════════════════════════════════════════════════════════════════════
#  O'chirish / Faollashtirish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cat:delete:"))
async def cat_delete(cb: CallbackQuery) -> None:
    await cb.answer("O'chirildi")
    _, _, ct, iid = cb.data.split(":")
    async with session_scope() as s:
        await get_repo(s, ct).update(int(iid), is_active=False)
        items = await list_items(s, ct)
    await safe_edit(cb, f"🗑 O'chirildi.\n\n{CATALOG_NAMES[ct]} ro'yxati:", catalog_list_kb(items, ct))


@router.callback_query(F.data.startswith("cat:activate:"))
async def cat_activate(cb: CallbackQuery) -> None:
    await cb.answer("Faollashtirildi")
    _, _, ct, iid = cb.data.split(":")
    iid = int(iid)
    async with session_scope() as s:
        await get_repo(s, ct).update(iid, is_active=True)
        item = await get_item(s, ct, iid)
    if not item:
        await cb.message.answer("❌ Topilmadi.")
        return
    await safe_edit(cb, build_item_text(ct, item), catalog_item_kb(ct, item.id, item.is_active))
