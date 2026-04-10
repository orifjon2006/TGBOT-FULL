"""Buyurtma yaratish jarayoni — to'liq flow."""

from __future__ import annotations

import uuid
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from google_sheets import append_order_to_sheet

from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from config import (
    BTN_BACK,
    DEFAULT_SERVICE_TREE,
    DEFAULT_SIMPLE_SERVICES,
)
from database import (
    ActiveJobRepository,
    CreateOrderDTO,
    Master,
    MasterRepository,
    NotFoundError,
    Order,
    OrderRepository,
    ServiceCatalog,
    UserRepository,
    ValidationError,
    VanHeight,
    VanHeightRepository,
    VehicleModel,
    VehicleModelRepository,
    session_scope,
)
from keyboards import (
    back_cancel_kb,
    confirm_kb,
    heights_kb,
    main_menu_kb,
    order_groups_kb,
    order_group_confirm_kb,
    selected_services_kb,
    service_children_kb,
    service_root_kb,
    skip_vin_kb,
    vehicle_models_kb,
)
from services import build_receipt_file, notify_masters_about_new_job
from states import OrderStates
from utils import (
    build_tree_label_from_path,
    format_amount,
    get_tree_node_by_path,
    html_escape,
    normalize_phone,
    parse_amount,
)

router = Router(name="order")


# ═══════════════════════════════════════════════════════════════════════════
#  Yordamchi
# ═══════════════════════════════════════════════════════════════════════════

async def safe_edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await cb.message.answer(text, reply_markup=markup)


async def get_or_create_service(service_name: str) -> int:
    async with session_scope() as session:
        item = await session.scalar(
            select(ServiceCatalog).where(ServiceCatalog.label == service_name)
        )
        if item:
            if not item.is_active:
                item.is_active = True
                await session.flush()
            return item.id
        item = ServiceCatalog(
            key=str(uuid.uuid4()),
            label=service_name,
            is_active=True,
            sort_order=0,
        )
        session.add(item)
        await session.flush()
        return item.id


async def add_service_to_state(state: FSMContext, service_label: str) -> tuple[bool, str]:
    data = await state.get_data()
    ids = list(data.get("selected_service_ids", []))
    labels = list(data.get("selected_service_labels", []))

    if service_label in labels:
        return False, "Bu xizmat allaqachon tanlangan."

    service_id = await get_or_create_service(service_label)
    ids.append(service_id)
    labels.append(service_label)

    await state.update_data(selected_service_ids=ids, selected_service_labels=labels)
    return True, "✅ Xizmat qo'shildi."


async def remove_service_by_index(state: FSMContext, index: int) -> str:
    data = await state.get_data()
    ids = list(data.get("selected_service_ids", []))
    labels = list(data.get("selected_service_labels", []))

    if index < 0 or index >= len(labels):
        return "Bunday xizmat topilmadi."
    removed = labels.pop(index)
    ids.pop(index)
    await state.update_data(selected_service_ids=ids, selected_service_labels=labels)
    return f"🗑 O'chirildi: {removed}"


def build_selected_text(labels: list[str]) -> str:
    if not labels:
        return "Hozircha tanlangan xizmat yo'q."
    lines = ["<b>Tanlangan xizmatlar</b>", ""]
    for i, label in enumerate(labels, 1):
        lines.append(f"{i}. {html_escape(label)}")
    return "\n".join(lines)


async def refresh_order_names(state: FSMContext) -> dict[str, Any]:
    data = await state.get_data()
    master_ids = data.get("master_ids", [])
    vehicle_model_id = data.get("vehicle_model_id")
    van_height_id = data.get("van_height_id")

    async with session_scope() as session:
        if vehicle_model_id:
            model = await session.get(VehicleModel, vehicle_model_id)
            if model:
                data["vehicle_model_name"] = model.name
        if master_ids:
            masters = await session.scalars(select(Master).where(Master.id.in_(master_ids)))
            m_map = {item.id: item.full_name for item in masters.all()}
            data["master_names"] = [m_map[mid] for mid in master_ids if mid in m_map]
        else:
            data["master_names"] = []

    await state.set_data(data)
    return data


async def build_summary_text(data: dict[str, Any]) -> str:
    model = data.get("vehicle_model_name") or "—"
    vin = data.get("vin_code") or "—"
    svc_labels = data.get("selected_service_labels", [])
    master_names = data.get("master_names", [])
    total = data.get("total_amount") or 0

    svcs = "\n".join(f"🔸 <i>{html_escape(n)}</i>" for n in svc_labels) if svc_labels else "—"
    masters = ", ".join(f"👨‍🔧 {html_escape(n)}" for n in master_names) if master_names else "—"

    return (
        "🔖 <b>YANGI BUYURTMA TAFSILOTLARI</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Mijoz:</b>  <code>{html_escape(data.get('client_name', '—'))}</code>\n"
        f"📞 <b>Telefon:</b>  <code>{html_escape(data.get('client_phone', '—'))}</code>\n"
        f"🚘 <b>Model:</b>  <code>{html_escape(model)}</code>\n"
        f"🔢 <b>VIN kod:</b>  <code>{html_escape(vin)}</code>\n\n"
        f"🛠 <b>Tanlangan xizmatlar:</b>\n{svcs}\n\n"
        f"👥 <b>Ustalar komandasi:</b>\n  {masters}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>Hisoblangan summa:</b>  <code>{format_amount(total)}</code>"
    )


async def clear_chat_history(message: Message, state: FSMContext, delete_user: bool = True) -> None:
    data = await state.get_data()
    msg_ids = data.get("prompt_msg_ids", [])
    if delete_user:
        try:
            await message.delete()
        except Exception:
            pass
    for mid in msg_ids:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
        except Exception:
            pass
    await state.update_data(prompt_msg_ids=[])

async def track_prompt(state: FSMContext, *msgs: Message) -> None:
    data = await state.get_data()
    ids = data.get("prompt_msg_ids", [])
    ids.extend(m.message_id for m in msgs)
    await state.update_data(prompt_msg_ids=ids)

# ═══════════════════════════════════════════════════════════════════════════
#  BOSQICH FUNKSIYALARI
# ═══════════════════════════════════════════════════════════════════════════

async def ask_client_name(msg: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.waiting_client_name)
    m = await msg.answer("👤 Mijoz ismini kiriting:", reply_markup=back_cancel_kb())
    await track_prompt(state, m)


async def ask_client_phone(msg: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.waiting_client_phone)
    m = await msg.answer("📞 Mijoz telefon raqamini kiriting:", reply_markup=back_cancel_kb())
    await track_prompt(state, m)


async def ask_vehicle_model(msg: Message, state: FSMContext) -> None:
    async with session_scope() as s:
        models = await VehicleModelRepository(s).list_active()
    await state.set_state(OrderStates.waiting_vehicle_model)
    m1 = await msg.answer("🚐 Mashina modelini tanlang:", reply_markup=ReplyKeyboardRemove())
    m2 = await msg.answer("Modelni tanlang yoki qo'lda kiriting:", reply_markup=vehicle_models_kb(models))
    await track_prompt(state, m1, m2)


async def ask_custom_model(msg: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.waiting_custom_vehicle_model)
    m = await msg.answer("⌨️ Model nomini qo'lda kiriting:", reply_markup=back_cancel_kb())
    await track_prompt(state, m)


async def ask_vin(msg: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.waiting_vin)
    m = await msg.answer("🔢 VIN kodini kiriting yoki qoldirib keting:", reply_markup=skip_vin_kb())
    await track_prompt(state, m)


async def ask_services(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    await state.set_state(OrderStates.waiting_services)
    m1 = await msg.answer("🛠 Xizmatlarni tanlang:", reply_markup=ReplyKeyboardRemove())
    m2 = await msg.answer(
        "Oddiy xizmat bir bosishda qo'shiladi.\n📂 belgisi — ichki bo'limlar mavjud.\n✏️ Yoki xizmat nomini qo'lda kiritishingiz mumkin.",
        reply_markup=service_root_kb(labels),
    )
    await track_prompt(state, m1, m2)


async def ask_total_amount(msg: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.waiting_total_amount)
    m = await msg.answer("💰 Umumiy summani kiriting. Masalan: 26000000", reply_markup=back_cancel_kb())
    await track_prompt(state, m)


# Balandlik qismi olib tashlandi


async def ask_group(msg: Message, state: FSMContext) -> None:
    async with session_scope() as s:
        from database import MasterGroupRepository
        groups = await MasterGroupRepository(s).list_active()
    await state.set_state(OrderStates.waiting_group)
    if not groups:
        m = await msg.answer("❌ Hech qanday usta guruhi mavjud emas. Oldin guruh yarating.")
        await track_prompt(state, m)
        return
    m = await msg.answer("👥 Buyurtmani qaysi guruhga tayinlaysiz?", reply_markup=order_groups_kb(groups))
    await track_prompt(state, m)


async def ask_confirmation(msg: Message, state: FSMContext) -> None:
    data = await refresh_order_names(state)
    await state.set_state(OrderStates.waiting_confirm)
    summary = await build_summary_text(data)
    m = await msg.answer(summary, reply_markup=confirm_kb())
    await track_prompt(state, m)


# ═══════════════════════════════════════════════════════════════════════════
#  BUYURTMA BOSHLASH
# ═══════════════════════════════════════════════════════════════════════════

from handlers.common import is_admin_like, is_main_admin

@router.message(F.text == "📝 Buyurtma yaratish")
async def start_order(message: Message, state: FSMContext) -> None:
    if not await is_admin_like(message.from_user.id):
        await message.answer("Bu bo'lim faqat adminlar uchun.")
        return
    await state.clear()
    await state.update_data(selected_service_ids=[], selected_service_labels=[], master_ids=[], prompt_msg_ids=[])
    await ask_client_name(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  1. MIJOZ ISMI
# ═══════════════════════════════════════════════════════════════════════════

@router.message(OrderStates.waiting_client_name, F.text == BTN_BACK)
async def back_from_client_name(message: Message, state: FSMContext) -> None:
    await clear_chat_history(message, state, True)
    await state.clear()
    from handlers.common import show_main_menu
    await show_main_menu(message, message.from_user.id)


@router.message(OrderStates.waiting_client_name)
async def process_client_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        m = await message.answer("❌ Ism juda qisqa. Qayta kiriting.")
        await track_prompt(state, m)
        return
    await state.update_data(client_name=name)
    await clear_chat_history(message, state, True)
    await ask_client_phone(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  2. MIJOZ TELEFON
# ═══════════════════════════════════════════════════════════════════════════

@router.message(OrderStates.waiting_client_phone, F.text == BTN_BACK)
async def back_from_phone(message: Message, state: FSMContext) -> None:
    await clear_chat_history(message, state, True)
    await ask_client_name(message, state)


@router.message(OrderStates.waiting_client_phone)
async def process_client_phone(message: Message, state: FSMContext) -> None:
    try:
        phone = normalize_phone(message.text or "")
    except ValueError as e:
        m = await message.answer(str(e))
        await track_prompt(state, m)
        return
    await state.update_data(client_phone=phone)
    await clear_chat_history(message, state, True)
    await ask_vehicle_model(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  3. MODELNI TANLASH
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("ord:model:"))
async def select_model(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    action = cb.data.split(":")[-1]

    if action == "manual":
        msg = cb.message
        await clear_chat_history(msg, state, False)
        # Buni ichida xabarni delete qilinmaydi chunki callback orqali keldi, shunchaki xabarni udalit qilamiz
        try:
            await msg.delete()
        except Exception:
            pass
        await ask_custom_model(cb.message, state)
        return

    model_id = int(action)
    async with session_scope() as s:
        model = await s.get(VehicleModel, model_id)
    if not model or not model.is_active:
        await cb.message.answer("❌ Model topilmadi yoki aktiv emas.")
        return

    await state.update_data(vehicle_model_id=model.id, vehicle_model_name=model.name, custom_vehicle_model_name=None)
    try:
        await cb.message.delete()
    except:
        pass
    await ask_vin(cb.message, state)


@router.callback_query(F.data == "ord:back:client_phone")
async def back_to_phone_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        await cb.message.delete()
    except:
        pass
    await ask_client_phone(cb.message, state)


@router.message(OrderStates.waiting_custom_vehicle_model, F.text == BTN_BACK)
async def back_from_custom_model(message: Message, state: FSMContext) -> None:
    await clear_chat_history(message, state, True)
    await ask_vehicle_model(message, state)


@router.message(OrderStates.waiting_custom_vehicle_model)
async def process_custom_model(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        m = await message.answer("❌ Model nomi juda qisqa.")
        await track_prompt(state, m)
        return
    await state.update_data(vehicle_model_id=None, vehicle_model_name=name, custom_vehicle_model_name=name)
    await clear_chat_history(message, state, True)
    await ask_vin(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  4. VIN KOD
# ═══════════════════════════════════════════════════════════════════════════

@router.message(OrderStates.waiting_vin, F.text == BTN_BACK)
async def back_from_vin(message: Message, state: FSMContext) -> None:
    await clear_chat_history(message, state, True)
    await ask_vehicle_model(message, state)


@router.message(OrderStates.waiting_vin)
async def process_vin(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    vin = None if text == "⏭ Qoldirib ketish" else (text or None)
    await state.update_data(vin_code=vin)
    await clear_chat_history(message, state, True)
    await ask_services(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  5. XIZMATLAR TANLASH
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "sv:root")
async def service_root(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    await safe_edit(cb, "🛠 Xizmatlarni tanlang:", service_root_kb(labels))


@router.callback_query(F.data.startswith("sv:o:"))
async def service_open_nested(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    raw = cb.data.split("sv:o:", 1)[1]
    path_keys = raw.split("|") if raw else []
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    node = get_tree_node_by_path(DEFAULT_SERVICE_TREE, path_keys)
    if node is None:
        await cb.message.answer("❌ Bo'lim topilmadi.")
        return
    title = build_tree_label_from_path(DEFAULT_SERVICE_TREE, path_keys)
    await safe_edit(cb, f"<b>{html_escape(title)}</b>\n\nIchki bo'limni tanlang:", service_children_kb(path_keys, labels))


@router.callback_query(F.data.startswith("sv:u:"))
async def service_go_up(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    raw = cb.data.split("sv:u:", 1)[1]
    path_keys = raw.split("|") if raw else []
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])

    if len(path_keys) <= 1:
        await safe_edit(cb, "🛠 Xizmatlarni tanlang:", service_root_kb(labels))
        return

    parent = path_keys[:-1]
    title = build_tree_label_from_path(DEFAULT_SERVICE_TREE, parent)
    await safe_edit(cb, f"<b>{html_escape(title)}</b>\n\nIchki bo'limni tanlang:", service_children_kb(parent, labels))


@router.callback_query(F.data.startswith("sv:a:"))
async def service_add_simple(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    key = cb.data.split("sv:a:", 1)[1]
    item = next((x for x in DEFAULT_SIMPLE_SERVICES if x["key"] == key), None)
    if item is None:
        await cb.message.answer("❌ Xizmat topilmadi.")
        return

    ok, msg = await add_service_to_state(state, item["label"])
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    await safe_edit(cb, f"{msg}\n\nJami tanlangan: {len(labels)} ta", service_root_kb(labels))


@router.callback_query(F.data.startswith("sv:s:"))
async def service_select_leaf(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    raw = cb.data.split("sv:s:", 1)[1]
    path_keys = raw.split("|") if raw else []
    label = build_tree_label_from_path(DEFAULT_SERVICE_TREE, path_keys)
    if not label:
        await cb.message.answer("❌ Xizmat topilmadi.")
        return

    ok, msg = await add_service_to_state(state, label)
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    await safe_edit(cb, f"{msg}\n\nJami tanlangan: {len(labels)} ta", service_root_kb(labels))


@router.callback_query(F.data == "sv:view")
async def service_view_selected(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    await safe_edit(cb, build_selected_text(labels), selected_services_kb(labels))


@router.callback_query(F.data.startswith("sv:r:"))
async def service_remove(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    idx = int(cb.data.split("sv:r:", 1)[1])
    msg = await remove_service_by_index(state, idx)
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    await safe_edit(cb, f"{msg}\n\n{build_selected_text(labels)}", selected_services_kb(labels))


@router.callback_query(F.data == "sv:done")
async def service_done(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("selected_service_ids"):
        await cb.answer("Kamida bitta xizmat tanlang", show_alert=True)
        return
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await ask_total_amount(cb.message, state)


@router.message(OrderStates.waiting_services)
async def process_manual_service(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        return
        
    await clear_chat_history(message, state, True)
    
    ok, msg_text = await add_service_to_state(state, text)
    data = await state.get_data()
    labels = data.get("selected_service_labels", [])
    
    m = await message.answer(
        f"{msg_text}\n\nJami tanlangan: {len(labels)} ta\n\nYana xizmat nomini qo'lda kiritishingiz yoki tugmalardan tanlashingiz mumkin.", 
        reply_markup=service_root_kb(labels)
    )
    await track_prompt(state, m)


@router.callback_query(F.data == "ord:back:vin")
async def back_to_vin(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await ask_vin(cb.message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  6. SUMMA
# ═══════════════════════════════════════════════════════════════════════════

@router.message(OrderStates.waiting_total_amount, F.text == BTN_BACK)
async def back_from_amount(message: Message, state: FSMContext) -> None:
    await clear_chat_history(message, state, True)
    await ask_services(message, state)


@router.message(OrderStates.waiting_total_amount)
async def process_amount(message: Message, state: FSMContext) -> None:
    try:
        total = parse_amount(message.text or "")
    except ValueError as e:
        m = await message.answer(str(e))
        await track_prompt(state, m)
        return
    await state.update_data(total_amount=int(total))
    await clear_chat_history(message, state, True)
    await ask_group(message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  7. USTALAR
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ord:back:amount")
async def back_to_amount(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        await cb.message.delete()
    except:
        pass
    await ask_total_amount(cb.message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  8. USTALAR
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("ord:grp:"))
async def handle_group_selection(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    parts = cb.data.split(":")
    action: str = parts[2]

    if action == "back_to_groups":
        await ask_group(cb.message, state)
        return

    group_id = int(parts[3])

    if action == "select":
        async with session_scope() as s:
            from database import MasterGroupRepository
            group = await MasterGroupRepository(s).get_by_id(group_id)
            masters = await MasterGroupRepository(s).get_masters_in_group(group_id)
        
        if not group:
            await cb.message.answer("Guruh topilmadi.")
            return

        if not masters:
            text = f"<b>{html_escape(group.name)}</b> guruhida ustalar yo'q. Boshqa guruh tanlang."
            await safe_edit(cb, text, order_group_confirm_kb(group_id))
            return
        
        master_names = "\n".join(f"👨‍🔧 {html_escape(m.full_name)}" for m in masters)
        text = (
            f"👥 <b>{html_escape(group.name)}</b> guruhini tanladingiz.\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Tarkibiga kiruvchi ustalar:\n"
            f"{master_names}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Bu guruhga buyurtma tayinlashni qabul qilasizmi?"
        )
        await safe_edit(cb, text, order_group_confirm_kb(group_id))
        return

    if action == "confirm":
        async with session_scope() as s:
            from database import MasterGroupRepository
            masters = await MasterGroupRepository(s).get_masters_in_group(group_id)
            m_ids = [m.id for m in masters]
        
        await state.update_data(assigned_group_id=group_id, master_ids=m_ids)
        try:
            await cb.message.delete()
        except:
            pass
        await ask_confirmation(cb.message, state)


@router.callback_query(F.data == "ord:back:group")
async def back_to_groups(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        await cb.message.delete()
    except:
        pass
    await ask_group(cb.message, state)


# ═══════════════════════════════════════════════════════════════════════════
#  9. TASDIQLASH VA SAQLASH
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ord:confirm:save")
async def confirm_and_save(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await cb.answer("Saqlanmoqda...")
    if not await is_admin_like(cb.from_user.id):
        await cb.message.answer("Bu bo'lim faqat adminlar uchun.")
        return

    data = await refresh_order_names(state)

    async with session_scope() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_telegram_id(cb.from_user.id)
        if not db_user:
            await cb.message.answer("❌ Admin topilmadi.")
            return

        service_names = list(data.get("selected_service_labels", []))
        master_names = list(data.get("master_names", []))
        assigned_group_id = data.get("assigned_group_id")

        order_repo = OrderRepository(session)
        dto = CreateOrderDTO(
            client_name=data["client_name"],
            client_phone=data["client_phone"],
            total_amount=data["total_amount"],
            created_by_user_id=db_user.id,
            confirmed_by_user_id=db_user.id,
            service_ids=service_names,
            master_ids=master_names,
            vehicle_model_id=data.get("vehicle_model_id"),
            custom_vehicle_model_name=data.get("custom_vehicle_model_name"),
            vin_code=data.get("vin_code"),
            van_height_id=None,
            assigned_group_id=assigned_group_id,
        )
        try:
            order = await order_repo.create_order(dto)
            job_repo = ActiveJobRepository(session)
            await job_repo.create_job(order_id=order.id, group_id=assigned_group_id)
            
            # Guruhdagi barcha aktiv ustalarni jadval uchun yig'amiz
            group_masters_res = await session.execute(select(Master).where(Master.group_id == assigned_group_id, Master.is_active == True))
            g_masters = group_masters_res.scalars().all()
            masters_str = ", ".join(m.full_name for m in g_masters) if g_masters else "Ustalar kiritilmagan"
            
            # --- GOOGLE SHEETS SYNC (Sana +1 kun qilingan) ---
            current_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            services_str = ", ".join(service_names)
            order_data = [
                str(order.id),
                order.client_name,
                services_str,
                f"{order.total_amount:,}",
                current_time,
                masters_str,        # Guruhdagi ustalar ismlari (qator bo'lib)
                "Kutilmoqda..."     # Tugallangan sana
            ]
            asyncio.create_task(asyncio.to_thread(append_order_to_sheet, order_data))
            # ---------------------------
            
        except (ValidationError, NotFoundError) as e:
            await cb.message.answer(f"❌ Xatolik: {e}")
            return

    await state.clear()

    try:
        await cb.message.delete()
    except:
        pass

    _is_main = await is_main_admin(cb.from_user.id)
    await cb.message.answer(
        f"✅ Buyurtma muvaffaqiyatli saqlandi!\n\n"
        f"<b>Mijoz kodi (Client Code):</b> {order.access_code}\n"
        f"<i>Ushbu kod orqali mijoz botdan o'z avtomobili holatini ko'ra oladi.</i>",
        reply_markup=main_menu_kb(_is_main),
    )

    # Chek yuborish
    file_path = build_receipt_file(order, service_names, master_names)
    try:
        doc = FSInputFile(file_path)
        await cb.message.answer_document(
            document=doc,
            caption=(
                f"✅ Zakaz №{order.order_number}\n"
                f"Mijoz: {order.client_name}\n"
                f"Mijoz kodi: <b>{order.access_code}</b>\n"
                f"Summa: {format_amount(order.total_amount)}"
            ),
        )
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Ustalarga xabar yuborish
    await notify_masters_about_new_job(bot, order, assigned_group_id)


# ═══════════════════════════════════════════════════════════════════════════
#  Tugma orqali tanlash kerak bo'lgan bosqichlar
# ═══════════════════════════════════════════════════════════════════════════

@router.message(OrderStates.waiting_vehicle_model)
@router.message(OrderStates.waiting_van_height)
@router.message(OrderStates.waiting_group)
@router.message(OrderStates.waiting_confirm)
async def order_buttons_only(message: Message) -> None:
    await message.answer("ℹ️ Bu bosqichda tugmalar orqali tanlang.")
