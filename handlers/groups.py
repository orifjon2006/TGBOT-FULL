"""Usta guruhlari boshqarish — yaratish, tahrirlash, o'chirish, a'zolar."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from config import BTN_BACK, BTN_MASTER_GROUPS
from database import MasterGroupRepository, MasterRepository, session_scope
from keyboards import back_cancel_kb, catalog_menu_kb, mg_detail_kb, mg_list_kb, mg_members_kb
from states import MasterGroupStates
from utils import html_escape

router = Router(name="groups")


async def safe_edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


# ═══════════════════════════════════════════════════════════════════════════
#  Guruhlar ro'yxati
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.text == BTN_MASTER_GROUPS)
async def show_groups(message: Message) -> None:
    from handlers.common import is_admin_like
    if not await is_admin_like(message.from_user.id):
        return
    async with session_scope() as s:
        groups = await MasterGroupRepository(s).list_active()
    await message.answer("👥 Usta guruhlari:", reply_markup=mg_list_kb(groups))


@router.callback_query(F.data == "mg:list")
async def groups_list_cb(cb: CallbackQuery) -> None:
    await cb.answer()
    async with session_scope() as s:
        groups = await MasterGroupRepository(s).list_active()
    await safe_edit(cb, "👥 Usta guruhlari:", mg_list_kb(groups))


@router.callback_query(F.data == "mg:back")
async def groups_back(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await cb.message.answer("🗂 Kataloglar:", reply_markup=catalog_menu_kb())


# ═══════════════════════════════════════════════════════════════════════════
#  Guruh ko'rish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mg:v:"))
async def group_view(cb: CallbackQuery) -> None:
    await cb.answer()
    gid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        g = await MasterGroupRepository(s).get_by_id(gid)
        members = await MasterGroupRepository(s).get_masters_in_group(gid) if g else []
    if not g:
        await cb.message.answer("❌ Topilmadi.")
        return
    mt = "\n".join(f"  • {m.full_name} [{m.access_code or '—'}]" for m in members) or "  Bo'sh"
    await safe_edit(cb, f"<b>👥 {html_escape(g.name)}</b>\n\n<b>A'zolar:</b>\n{mt}", mg_detail_kb(gid))


# ═══════════════════════════════════════════════════════════════════════════
#  Guruh qo'shish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "mg:add")
async def group_add_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(MasterGroupStates.waiting_group_name)
    await cb.message.answer("📝 Yangi guruh nomini kiriting:", reply_markup=back_cancel_kb())


@router.message(MasterGroupStates.waiting_group_name, F.text == BTN_BACK)
async def group_add_back(msg: Message, state: FSMContext) -> None:
    await state.clear()
    async with session_scope() as s:
        groups = await MasterGroupRepository(s).list_active()
    await msg.answer("Guruhlar:", reply_markup=ReplyKeyboardRemove())
    await msg.answer("👥 Usta guruhlari:", reply_markup=mg_list_kb(groups))


@router.message(MasterGroupStates.waiting_group_name)
async def group_add_name(msg: Message, state: FSMContext) -> None:
    name = (msg.text or "").strip()
    if len(name) < 2:
        await msg.answer("❌ Nom juda qisqa.")
        return
    async with session_scope() as s:
        await MasterGroupRepository(s).create(name)
        groups = await MasterGroupRepository(s).list_active()
    await state.clear()
    await msg.answer("✅ Guruh yaratildi.", reply_markup=ReplyKeyboardRemove())
    await msg.answer("👥 Usta guruhlari:", reply_markup=mg_list_kb(groups))


# ═══════════════════════════════════════════════════════════════════════════
#  Nom o'zgartirish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mg:ren:"))
async def group_rename_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    gid = int(cb.data.split(":")[-1])
    await state.update_data(mg_ren_id=gid)
    await state.set_state(MasterGroupStates.waiting_group_rename)
    await cb.message.answer("✏️ Yangi nomni kiriting:", reply_markup=back_cancel_kb())


@router.message(MasterGroupStates.waiting_group_rename, F.text == BTN_BACK)
async def group_rename_back(msg: Message, state: FSMContext) -> None:
    await state.clear()
    async with session_scope() as s:
        groups = await MasterGroupRepository(s).list_active()
    await msg.answer("Guruhlar:", reply_markup=ReplyKeyboardRemove())
    await msg.answer("👥 Usta guruhlari:", reply_markup=mg_list_kb(groups))


@router.message(MasterGroupStates.waiting_group_rename)
async def group_rename_process(msg: Message, state: FSMContext) -> None:
    name = (msg.text or "").strip()
    if len(name) < 2:
        await msg.answer("❌ Nom juda qisqa.")
        return
    data = await state.get_data()
    gid = data.get("mg_ren_id")
    async with session_scope() as s:
        await MasterGroupRepository(s).update(gid, name=name)
        groups = await MasterGroupRepository(s).list_active()
    await state.clear()
    await msg.answer("✅ Nom yangilandi.", reply_markup=ReplyKeyboardRemove())
    await msg.answer("👥 Usta guruhlari:", reply_markup=mg_list_kb(groups))


# ═══════════════════════════════════════════════════════════════════════════
#  O'chirish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mg:del:"))
async def group_delete(cb: CallbackQuery) -> None:
    await cb.answer("O'chirildi")
    gid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        await MasterGroupRepository(s).delete(gid)
        groups = await MasterGroupRepository(s).list_active()
    await safe_edit(cb, "👥 Usta guruhlari:", mg_list_kb(groups))


# ═══════════════════════════════════════════════════════════════════════════
#  A'zolar boshqarish
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("mg:mem:"))
async def group_members(cb: CallbackQuery) -> None:
    await cb.answer()
    gid = int(cb.data.split(":")[-1])
    async with session_scope() as s:
        masters = await MasterRepository(s).list_active()
    await safe_edit(cb, "Ustani guruhga qo'shish/olib tashlash:", mg_members_kb(masters, gid))


@router.callback_query(F.data.startswith("mg:tg:"))
async def group_toggle_member(cb: CallbackQuery) -> None:
    await cb.answer()
    parts = cb.data.split(":")
    gid, mid = int(parts[2]), int(parts[3])
    async with session_scope() as s:
        repo = MasterRepository(s)
        m = await repo.get_by_id(mid)
        if m:
            await repo.set_group(mid, None if m.group_id == gid else gid)
        masters = await repo.list_active()
    await safe_edit(cb, "Ustani guruhga qo'shish/olib tashlash:", mg_members_kb(masters, gid))
