"""Barcha klaviaturalar — reply va inline."""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import (
    BTN_ACTIVE_JOBS,
    BTN_APPROVALS,
    BTN_BACK,
    BTN_CANCEL,
    BTN_CATALOGS,
    BTN_CREATE_ORDER,
    BTN_EXPORT_EXCEL,
    BTN_EXTRA,
    BTN_HEIGHTS,
    BTN_LICENSE_ADD,
    BTN_LICENSE_CHECK,
    BTN_MASTER_GROUPS,
    BTN_MASTERS,
    BTN_MODELS,
    BTN_ORDER_HISTORY,
    BTN_REFRESH,
    BTN_REGISTER_SUBADMIN,
    BTN_SEARCH_CLIENT,
    BTN_SERVICES,
    BTN_STATISTICS,
    CATALOG_NAMES,
    DEFAULT_SERVICE_TREE,
    DEFAULT_SIMPLE_SERVICES,
)
from utils import truncate


# ═══════════════════════════════════════════════════════════════════════════
#  REPLY KLAVIATURALAR
# ═══════════════════════════════════════════════════════════════════════════

def main_menu_kb(is_main_admin: bool) -> ReplyKeyboardMarkup:
    """Bosh menu — faqat asosiy kundalik tugmalar."""
    b = ReplyKeyboardBuilder()
    b.button(text=BTN_CREATE_ORDER)
    b.button(text=BTN_SEARCH_CLIENT)
    b.button(text=BTN_ACTIVE_JOBS)
    b.button(text=BTN_STATISTICS)
    b.button(text=BTN_EXTRA)
    b.button(text=BTN_REFRESH)
    b.adjust(2, 2, 2)
    return b.as_markup(resize_keyboard=True)


def extra_menu_kb(is_main_admin: bool) -> ReplyKeyboardMarkup:
    """Qo'shimcha menu — boshqaruv va kamroq ishlatiladigan tugmalar."""
    b = ReplyKeyboardBuilder()
    
    b.button(text=BTN_LICENSE_ADD)
    b.button(text=BTN_LICENSE_CHECK)
    
    b.button(text=BTN_CATALOGS)
    b.button(text=BTN_ORDER_HISTORY)
    b.button(text=BTN_EXPORT_EXCEL)
    b.button(text=BTN_MASTER_GROUPS)
    
    if is_main_admin:
        b.button(text=BTN_APPROVALS)
    b.button(text=BTN_BACK)
    if is_main_admin:
        b.adjust(2, 2, 2, 1, 1)
    else:
        b.adjust(2, 2, 2, 1)
    return b.as_markup(resize_keyboard=True)


def guest_kb() -> ReplyKeyboardMarkup:
    # Deprecated
    pass


def back_cancel_kb() -> ReplyKeyboardMarkup:
    """Ortga + Bekor qilish."""
    b = ReplyKeyboardBuilder()
    b.button(text=BTN_BACK)
    b.button(text=BTN_CANCEL)
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)


def catalog_menu_kb() -> ReplyKeyboardMarkup:
    """Kataloglar submenu."""
    b = ReplyKeyboardBuilder()
    b.button(text=BTN_MODELS)
    b.button(text=BTN_SERVICES)
    b.button(text=BTN_HEIGHTS)
    b.button(text=BTN_MASTERS)
    b.button(text=BTN_BACK)
    b.adjust(2, 2, 1)
    return b.as_markup(resize_keyboard=True)


def skip_vin_kb() -> ReplyKeyboardMarkup:
    """VIN kiritish yoki o'tkazib yuborish."""
    b = ReplyKeyboardBuilder()
    b.button(text="⏭ Qoldirib ketish")
    b.button(text=BTN_BACK)
    b.button(text=BTN_CANCEL)
    b.adjust(1, 2)
    return b.as_markup(resize_keyboard=True)


def master_home_kb() -> ReplyKeyboardMarkup:
    """Usta bosh menu."""
    b = ReplyKeyboardBuilder()
    b.button(text="📋 Mening ishlarim")
    b.adjust(1)
    return b.as_markup(resize_keyboard=True)


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Katalog
# ═══════════════════════════════════════════════════════════════════════════

def catalog_list_kb(items: list[Any], catalog_type: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for item in items:
        title = (
            getattr(item, "name", None)
            or getattr(item, "label", None)
            or getattr(item, "full_name", None)
            or f"ID {item.id}"
        )
        b.row(
            InlineKeyboardButton(
                text=f"#{item.id} • {truncate(title, 45)}",
                callback_data=f"cat:item:{catalog_type}:{item.id}",
            )
        )
    b.row(
        InlineKeyboardButton(text="➕ Qo'shish", callback_data=f"cat:add:{catalog_type}"),
        InlineKeyboardButton(text=BTN_BACK, callback_data="cat:menu"),
    )
    return b.as_markup()


def catalog_item_kb(catalog_type: str, item_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"cat:rename:{catalog_type}:{item_id}"))
    b.row(InlineKeyboardButton(text="↕️ Tartib raqami", callback_data=f"cat:sort:{catalog_type}:{item_id}"))
    if catalog_type == "masters":
        b.row(InlineKeyboardButton(text="📞 Telefon", callback_data=f"cat:phone:{catalog_type}:{item_id}"))
    if is_active:
        b.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"cat:delete:{catalog_type}:{item_id}"))
    else:
        b.row(InlineKeyboardButton(text="♻️ Faollashtirish", callback_data=f"cat:activate:{catalog_type}:{item_id}"))
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data=f"cat:list:{catalog_type}"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Buyurtma yaratish
# ═══════════════════════════════════════════════════════════════════════════

def vehicle_models_kb(models: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for model in models:
        b.button(text=model.name, callback_data=f"ord:model:{model.id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⌨️ Qo'lda kiritish", callback_data="ord:model:manual"))
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="ord:back:client_phone"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


def heights_kb(items: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for item in items:
        b.row(InlineKeyboardButton(text=item.name, callback_data=f"ord:height:{item.id}"))
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="ord:back:amount"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


def order_groups_kb(groups: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in groups:
        b.button(text=f"👥 {g.name}", callback_data=f"ord:grp:select:{g.id}")
    b.adjust(2)
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="ord:back:amount"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


def order_group_confirm_kb(group_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Shu guruhni tanlash", callback_data=f"ord:grp:confirm:{group_id}"))
    b.row(
        InlineKeyboardButton(text="⬅️ Boshqa guruh", callback_data="ord:grp:back_to_groups"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💾 Tasdiqlash va saqlash", callback_data="ord:confirm:save"))
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="ord:back:masters"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Xizmat tanlash (daraxt)
# ═══════════════════════════════════════════════════════════════════════════

def service_root_kb(selected_labels: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    # Daraxtdagi guruhlar
    for root_key, root_node in DEFAULT_SERVICE_TREE.items():
        b.button(
            text=f"📂 {truncate(root_node['label'], 42)}",
            callback_data=f"sv:o:{root_key}",
        )

    # Oddiy xizmatlar
    for item in DEFAULT_SIMPLE_SERVICES:
        prefix = "✅" if item['label'] in selected_labels else "➕"
        b.button(
            text=f"{prefix} {truncate(item['label'], 42)}",
            callback_data=f"sv:a:{item['key']}",
        )
        
    b.adjust(2)

    b.row(
        InlineKeyboardButton(text=f"📋 Tanlangan ({len(selected_labels)})", callback_data="sv:view"),
        InlineKeyboardButton(text="✅ Tayyor", callback_data="sv:done"),
    )
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="ord:back:vin"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


def service_children_kb(path_keys: list[str], selected_labels: list[str]) -> InlineKeyboardMarkup:
    from utils import build_tree_label_from_path, get_tree_node_by_path
    node = get_tree_node_by_path(DEFAULT_SERVICE_TREE, path_keys)
    b = InlineKeyboardBuilder()

    if node is None:
        b.row(
            InlineKeyboardButton(text=BTN_BACK, callback_data="sv:root"),
            InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
        )
        return b.as_markup()

    children = node.get("children", {})
    for child_key, child_node in children.items():
        child_path = path_keys + [child_key]
        if child_node.get("children"):
            b.button(
                text=f"📂 {truncate(child_node['label'], 42)}",
                callback_data=f"sv:o:{'|'.join(child_path)}",
            )
        else:
            full_label = build_tree_label_from_path(DEFAULT_SERVICE_TREE, child_path)
            prefix = "✅" if full_label in selected_labels else "➕"
            b.button(
                text=f"{prefix} {truncate(child_node['label'], 42)}",
                callback_data=f"sv:s:{'|'.join(child_path)}",
            )

    b.adjust(2)

    b.row(
        InlineKeyboardButton(text=f"📋 Tanlangan ({len(selected_labels)})", callback_data="sv:view"),
        InlineKeyboardButton(text="🏠 Xizmatlar boshiga", callback_data="sv:root"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Bir pog'ona ortga", callback_data=f"sv:u:{'|'.join(path_keys)}"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


def selected_services_kb(selected_labels: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for index, label in enumerate(selected_labels):
        b.row(
            InlineKeyboardButton(
                text=f"🗑 {truncate(label, 42)}",
                callback_data=f"sv:r:{index}",
            )
        )
    b.row(
        InlineKeyboardButton(text="🏠 Xizmatlar boshiga", callback_data="sv:root"),
        InlineKeyboardButton(text="✅ Tayyor", callback_data="sv:done"),
    )
    b.row(
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Admin so'rovlari
# ═══════════════════════════════════════════════════════════════════════════

def pending_admins_kb(users: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not users:
        b.row(InlineKeyboardButton(text=BTN_BACK, callback_data="adm:back:menu"))
        return b.as_markup()
    for user in users:
        b.row(
            InlineKeyboardButton(
                text=f"#{user.id} • {truncate(user.full_name, 45)}",
                callback_data=f"adm:view:{user.id}",
            )
        )
    b.row(InlineKeyboardButton(text=BTN_BACK, callback_data="adm:back:menu"))
    return b.as_markup()


def pending_admin_actions_kb(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adm:approve:{user_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"adm:reject:{user_id}"),
    )
    b.row(InlineKeyboardButton(text=BTN_BACK, callback_data="adm:list"))
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Qidiruv
# ═══════════════════════════════════════════════════════════════════════════

def search_type_kb() -> InlineKeyboardMarkup:
    """Qidiruv turi tanlash."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📞 Telefon bo'yicha", callback_data="srch:type:phone"))
    b.row(InlineKeyboardButton(text="👤 Ism bo'yicha", callback_data="srch:type:name"))
    b.row(InlineKeyboardButton(text="🚐 Model bo'yicha", callback_data="srch:type:model"))
    b.row(InlineKeyboardButton(text="🔢 VIN bo'yicha", callback_data="srch:type:vin"))
    b.row(InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"))
    return b.as_markup()


def search_result_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📝 Text ko'rinishida", callback_data="search:show_text"))
    b.row(InlineKeyboardButton(text="📄 Excel ko'rinishida", callback_data="search:show_excel"))
    b.row(
        InlineKeyboardButton(text="🔍 Yangi qidiruv", callback_data="search:new"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Usta guruhlari
# ═══════════════════════════════════════════════════════════════════════════

def mg_list_kb(groups: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in groups:
        b.row(InlineKeyboardButton(text=f"👥 {truncate(g.name, 40)}", callback_data=f"mg:v:{g.id}"))
    b.row(
        InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="mg:add"),
        InlineKeyboardButton(text=BTN_BACK, callback_data="mg:back"),
    )
    return b.as_markup()


def mg_detail_kb(gid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👨‍🔧 Ustalarni boshqarish", callback_data=f"mg:mem:{gid}"))
    b.row(InlineKeyboardButton(text="✏️ Nom o'zgartirish", callback_data=f"mg:ren:{gid}"))
    b.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"mg:del:{gid}"))
    b.row(InlineKeyboardButton(text=BTN_BACK, callback_data="mg:list"))
    return b.as_markup()


def mg_members_kb(masters: list, gid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in masters:
        pfx = "✅" if m.group_id == gid else "☑️"
        code = f" [{m.access_code}]" if m.access_code else ""
        b.row(InlineKeyboardButton(text=f"{pfx} {m.full_name}{code}", callback_data=f"mg:tg:{gid}:{m.id}"))
    b.row(InlineKeyboardButton(text=BTN_BACK, callback_data=f"mg:v:{gid}"))
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Amaldagi ishlar
# ═══════════════════════════════════════════════════════════════════════════

def single_active_job_kb(job_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="🔄 Boshqa guruhga o'tkazish",
        callback_data=f"aj:re:{job_id}",
    ))
    return b.as_markup()


def reassign_groups_kb(job_id: int, groups: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in groups:
        b.row(InlineKeyboardButton(text=f"👥 {g.name}", callback_data=f"aj:mv:{job_id}:{g.id}"))
    b.row(InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"))
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Usta paneli
# ═══════════════════════════════════════════════════════════════════════════

def master_jobs_kb(items: list[tuple]) -> InlineKeyboardMarkup:
    """items: list of (job, order) tuples."""
    b = InlineKeyboardBuilder()
    for job, order in items:
        b.row(InlineKeyboardButton(
            text=f"🚐 #{order.id} — {truncate(order.vehicle_model or '—', 28)}",
            callback_data=f"mj:v:{job.id}",
        ))
    return b.as_markup()


def master_job_detail_kb(jid: int, started: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not started:
        b.row(InlineKeyboardButton(text="▶️ Ishni boshlash", callback_data=f"mj:start:{jid}"))
    b.row(InlineKeyboardButton(text="✅ Xizmat bajarildi", callback_data=f"mj:done:{jid}"))
    b.row(InlineKeyboardButton(text="⬅️ Ortga", callback_data="mj:list"))
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Statistika
# ═══════════════════════════════════════════════════════════════════════════

def statistics_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📅 Bugun", callback_data="stat:view:today:0"))
    b.row(InlineKeyboardButton(text="📆 Bu hafta", callback_data="stat:view:week:0"))
    b.row(InlineKeyboardButton(text="🗓 Bu oy", callback_data="stat:view:month:0"))
    b.row(InlineKeyboardButton(text="📊 Barcha vaqt", callback_data="stat:view:all:0"))
    b.row(InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"))
    return b.as_markup()

def statistics_result_kb(period: str, groups: list, current_group_id: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    excel_text = "📥 Umumiy Excel"
    if current_group_id != 0:
        for g in groups:
            if g.id == current_group_id:
                excel_text = f"📥 {truncate(g.name, 25)} Exceli"
                break
                
    b.row(InlineKeyboardButton(text=excel_text, callback_data=f"stat:ex:{period}:{current_group_id}"))
    
    pfx = "☑️" if current_group_id == 0 else "🏢"
    b.row(InlineKeyboardButton(text=f"{pfx} Umumiy statistika", callback_data=f"stat:view:{period}:0"))
    
    # Ikkitadan qilib chiqarish usta guruhlarini
    row_btns = []
    for g in groups:
        p_btn = "✅" if current_group_id == g.id else "🏢"
        row_btns.append(InlineKeyboardButton(text=f"{p_btn} {truncate(g.name, 15)}", callback_data=f"stat:view:{period}:{g.id}"))
        if len(row_btns) == 2:
            b.row(*row_btns)
            row_btns = []
    if row_btns:
        b.row(*row_btns)
        
    b.row(InlineKeyboardButton(text=BTN_BACK, callback_data="stat:back"))
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
#  INLINE KLAVIATURALAR — Buyurtma boshqarish
# ═══════════════════════════════════════════════════════════════════════════

def order_history_kb(orders: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * per_page
    end = start + per_page
    page_orders = orders[start:end]

    for order in page_orders:
        emoji = order.status_emoji
        b.row(InlineKeyboardButton(
            text=f"{emoji} #{order.id} — {truncate(order.client_name, 25)} — {truncate(order.vehicle_model or '—', 15)}",
            callback_data=f"oh:v:{order.id}",
        ))

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"oh:page:{page - 1}"))
    if end < len(orders):
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"oh:page:{page + 1}"))
    if nav_row:
        b.row(*nav_row)

    b.row(InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"))
    return b.as_markup()


def order_manage_kb(order_id: int, is_active: bool = True, vin: str = "") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_active:
        b.row(InlineKeyboardButton(text="💰 Summani o'zgartirish", callback_data=f"om:amount:{order_id}"))
        b.row(InlineKeyboardButton(text="📝 Izoh qo'shish", callback_data=f"om:comment:{order_id}"))
        b.row(InlineKeyboardButton(text="🔴 Bekor qilish", callback_data=f"om:cancel:{order_id}"))
    b.row(InlineKeyboardButton(text="📄 Chek yuklab olish", callback_data=f"om:receipt:{order_id}"))
    if vin:
        b.row(InlineKeyboardButton(text="📜 Litsenziya", callback_data=f"lic:view:{vin}"))
    b.row(
        InlineKeyboardButton(text=BTN_BACK, callback_data="oh:list"),
        InlineKeyboardButton(text=BTN_CANCEL, callback_data="global:cancel"),
    )
    return b.as_markup()
