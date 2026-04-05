"""Xizmat modullari — chek yaratish, Excel eksport, notifikatsiya."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from config import (
    COMPANY_NAME,
    COMPANY_PHONE_1,
    COMPANY_PHONE_2,
    COMPANY_TELEGRAM,
    TEMP_RECEIPT_DIR,
    TEMP_STAT_DIR,
)
from utils import format_amount, html_escape, now_ts


# ═══════════════════════════════════════════════════════════════════════════
#  CHEK YARATISH
# ═══════════════════════════════════════════════════════════════════════════

def build_receipt_file(order, service_names: list[str], master_names: list[str]) -> Path:
    """Buyurtma chekini Excel formatda yaratish."""
    target_dir = Path(TEMP_RECEIPT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"check_order_{order.order_number}_{now_ts()}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Chek"

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 5
    ws.column_dimensions["F"].width = 22
    ws.column_dimensions["G"].width = 24
    ws.column_dimensions["H"].width = 24
    ws.column_dimensions["I"].width = 18

    for row in range(1, 40):
        ws.row_dimensions[row].height = 22

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    title_fill = PatternFill("solid", fgColor="D9EAF7")
    section_fill = PatternFill("solid", fgColor="F2F2F2")

    def draw_receipt(start_col: str, show_price: bool):
        c1, c2, c3, c4 = ("A", "B", "C", "D") if start_col == "A" else ("F", "G", "H", "I")

        ws.merge_cells(f"{c1}1:{c4}1")
        ws[f"{c1}1"] = COMPANY_NAME
        ws[f"{c1}1"].font = Font(size=16, bold=True)
        ws[f"{c1}1"].alignment = center

        ws.merge_cells(f"{c1}2:{c4}2")
        ws[f"{c1}2"] = "Xizmat cheki / Service Receipt"
        ws[f"{c1}2"].font = Font(size=12, bold=True)
        ws[f"{c1}2"].alignment = center
        ws[f"{c1}2"].fill = title_fill

        info_rows = [
            (4, "Тел. Номер", order.client_phone),
            (5, "Заказ №", str(order.order_number)),
            (6, "Ф.И.О", order.client_name),
            (7, "Модель", order.vehicle_model_name_snapshot),
            (8, "VIN КОДИ", order.vin_code or "—"),
            (9, "Сана", order.confirmed_at.strftime("%d.%m.%Y") if order.confirmed_at else "—"),
            (10, "Размер Фургона", order.van_height_name_snapshot),
            (11, "Усталар", ", ".join(master_names) if master_names else "—"),
        ]

        for row, label, value in info_rows:
            ws[f"{c1}{row}"] = label
            ws[f"{c1}{row}"].font = Font(bold=True)
            ws[f"{c1}{row}"].border = border
            ws[f"{c1}{row}"].alignment = left

            ws.merge_cells(f"{c2}{row}:{c4}{row}")
            ws[f"{c2}{row}"] = value
            ws[f"{c2}{row}"].border = border
            ws[f"{c2}{row}"].alignment = left

        ws.merge_cells(f"{c1}13:{c4}15")
        ws[f"{c1}13"] = (
            f'Хизмат курсатди\n"{COMPANY_NAME}"\n'
            f"{COMPANY_PHONE_1}\n{COMPANY_PHONE_2}\nТелеграмм {COMPANY_TELEGRAM}"
        )
        ws[f"{c1}13"].alignment = center
        ws[f"{c1}13"].font = Font(bold=True)
        ws[f"{c1}13"].fill = section_fill
        ws[f"{c1}13"].border = border

        ws.merge_cells(f"{c1}17:{c3}17")
        ws[f"{c1}17"] = "Услуга"
        ws[f"{c4}17"] = "Сумма" if show_price else " "

        for cell in [ws[f"{c1}17"], ws[f"{c4}17"]]:
            cell.font = Font(bold=True)
            cell.alignment = center
            cell.fill = title_fill
            cell.border = border

        for col in [c2, c3]:
            ws[f"{col}17"].border = border
            ws[f"{col}17"].fill = title_fill

        start_row = 18
        s_names = service_names if service_names else ["—"]

        for index, service_name in enumerate(s_names, start=0):
            row = start_row + index
            ws.merge_cells(f"{c1}{row}:{c3}{row}")
            ws[f"{c1}{row}"] = service_name
            ws[f"{c1}{row}"].alignment = left
            ws[f"{c1}{row}"].border = border
            ws[f"{c4}{row}"] = ""
            ws[f"{c4}{row}"].border = border
            ws[f"{c4}{row}"].alignment = center

        total_row = start_row + len(s_names)
        ws.merge_cells(f"{c1}{total_row}:{c3}{total_row}")
        ws[f"{c1}{total_row}"] = "ИТОГО"
        ws[f"{c1}{total_row}"].font = Font(bold=True)
        ws[f"{c1}{total_row}"].alignment = center
        ws[f"{c1}{total_row}"].fill = title_fill
        ws[f"{c1}{total_row}"].border = border

        if show_price:
            ws[f"{c4}{total_row}"] = format_amount(order.total_amount)
        else:
            ws[f"{c4}{total_row}"] = ""

        ws[f"{c4}{total_row}"].font = Font(bold=True)
        ws[f"{c4}{total_row}"].alignment = center
        ws[f"{c4}{total_row}"].fill = title_fill
        ws[f"{c4}{total_row}"].border = border

        sign_row = total_row + 2
        ws.merge_cells(f"{c1}{sign_row}:{c4}{sign_row}")
        ws[f"{c1}{sign_row}"] = "Rahmat. Zakaz ma'lumoti bazaga va umumiy Excel hisobotga yozildi."
        ws[f"{c1}{sign_row}"].alignment = center
        ws[f"{c1}{sign_row}"].font = Font(italic=True)

    draw_receipt("A", show_price=True)
    draw_receipt("F", show_price=False)

    wb.save(file_path)
    return file_path


# ═══════════════════════════════════════════════════════════════════════════
#  MIJOZ QIDIRUV EXCEL
# ═══════════════════════════════════════════════════════════════════════════

import re
from openpyxl.styles import Font, PatternFill, Alignment

def sanitize_for_excel(val):
    if val is None:
        return "—"
    if isinstance(val, str):
        # XML control characters
        val = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', val)
        # Barcha emojilar va BMP dan tashqari belgilarni (U+FFFF dan yuqori) o'chirish
        val = re.sub(r'[^\u0000-\uFFFF]', '', val)
        # Excel formula xatolarining oldini olish
        if val.startswith("=") or val.startswith("+") or val.startswith("-") or val.startswith("@"):
            val = "'" + val
        return val.strip()
    return val

def build_search_excel(client_query: str, orders: list) -> Path:
    """Qidiruv natijasini Excel formatda yaratish."""
    target_dir = Path(TEMP_RECEIPT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(ch for ch in client_query if ch.isalnum()) or "search"
    file_path = target_dir / f"search_{safe_name}_{now_ts()}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Qidiruv natijasi"

    headers = [
        "Zakaz №", "Sana", "Mijoz ismi", "Telefon",
        "Model", "VIN kodi", "Xizmatlar", "Umumiy summa",
        "Furgon balandligi", "Ustalar", "Holat",
    ]
    ws.append(headers)

    for order in orders:
        svc_text = ", ".join(order.service_names_list) or "—"
        masters_text = ", ".join(order.master_names_list) or "—"
        status_text = {"active": "Aktiv", "completed": "Bajarilgan", "cancelled": "Bekor"}.get(
            order.status or "active", "—"
        )

        ws.append([
            sanitize_for_excel(order.order_number),
            sanitize_for_excel(order.confirmed_at.strftime("%d.%m.%Y") if order.confirmed_at else "—"),
            sanitize_for_excel(order.client_name),
            sanitize_for_excel(order.client_phone),
            sanitize_for_excel(order.vehicle_model_name_snapshot),
            sanitize_for_excel(order.vin_code or ""),
            sanitize_for_excel(svc_text),
            sanitize_for_excel(svc_text),
            float(order.total_amount or 0),
            sanitize_for_excel(order.van_height_name_snapshot),
            sanitize_for_excel(masters_text),
            sanitize_for_excel(status_text),
        ])

    hdr_fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    if len(orders) > 0:
        ws.auto_filter.ref = f"A1:K{len(orders)+1}"

    widths = {1: 12, 2: 14, 3: 28, 4: 20, 5: 24, 6: 24, 7: 48, 8: 18, 9: 16, 10: 35, 11: 12}
    for idx, width in widths.items():
        ws.column_dimensions[chr(64 + idx)].width = width
    ws.freeze_panes = "A2"

    wb.save(file_path)
    return file_path


# ═══════════════════════════════════════════════════════════════════════════
#  UMUMIY EXCEL EKSPORT
# ═══════════════════════════════════════════════════════════════════════════

def build_all_orders_excel(orders: list) -> Path:
    """Barcha buyurtmalarni Excel ga eksport qilish."""
    target_dir = Path(TEMP_STAT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"all_orders_{now_ts()}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Barcha buyurtmalar"

    headers = [
        "№", "Kod", "Sana", "Mijoz", "Telefon", "Model", "VIN",
        "Xizmatlar", "Summa", "Balandlik", "Ustalar", "Guruh ID",
        "Holat", "Izoh",
    ]
    ws.append(headers)

    for order in orders:
        svc_text = ", ".join(order.service_names_list) or "—"
        masters_text = ", ".join(order.master_names_list) or "—"
        status_text = {"active": "Aktiv", "completed": "Bajarilgan", "cancelled": "Bekor"}.get(
            order.status or "active", "—"
        )
        ws.append([
            sanitize_for_excel(order.order_number),
            sanitize_for_excel(order.access_code or "—"),
            sanitize_for_excel(order.confirmed_at.strftime("%d.%m.%Y %H:%M") if order.confirmed_at else "—"),
            sanitize_for_excel(order.client_name),
            sanitize_for_excel(order.client_phone),
            sanitize_for_excel(order.vehicle_model_name_snapshot),
            sanitize_for_excel(order.vin_code or ""),
            sanitize_for_excel(svc_text),
            float(order.total_amount or 0),
            sanitize_for_excel(order.van_height_name_snapshot),
            sanitize_for_excel(masters_text),
            sanitize_for_excel(str(order.assigned_group_id) if order.assigned_group_id else "—"),
            sanitize_for_excel(status_text),
            sanitize_for_excel(order.comment or ""),
        ])

    hdr_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    white_font = Font(bold=True, color="FFFFFF")
    
    for cell in ws[1]:
        cell.font = white_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    if len(orders) > 0:
        ws.auto_filter.ref = f"A1:N{len(orders)+1}"

    widths = {1: 8, 2: 10, 3: 18, 4: 28, 5: 20, 6: 24, 7: 20, 8: 48, 9: 18, 10: 16, 11: 35, 12: 12, 13: 14, 14: 40}
    for idx, width in widths.items():
        ws.column_dimensions[chr(64 + idx)].width = width
    ws.freeze_panes = "A2"

    wb.save(file_path)
    return file_path


# ═══════════════════════════════════════════════════════════════════════════
#  STATISTIKA EXCEL
# ═══════════════════════════════════════════════════════════════════════════

def build_stats_excel(stats: dict, period_label: str) -> Path:
    """Statistikani Excel ga eksport."""
    target_dir = Path(TEMP_STAT_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"stats_{now_ts()}.xlsx"

    wb = Workbook()

    # Umumiy sahifa
    ws = wb.active
    ws.title = "Umumiy"
    ws.append(["Ko'rsatkich", "Qiymat"])
    ws.append(["Davr", sanitize_for_excel(period_label)])
    ws.append(["Jami buyurtmalar", stats["total_count"]])
    ws.append(["Aktiv", stats["active_count"]])
    ws.append(["Bajarilgan", stats["completed_count"]])
    ws.append(["Bekor qilingan", stats["cancelled_count"]])
    ws.append(["Umumiy summa", float(stats["total_amount"] or 0)])
    
    hdr_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    for row in ws.iter_rows(min_row=1, max_row=6, max_col=1):
        for cell in row:
            cell.font = Font(bold=True)
            cell.fill = hdr_fill

    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 20

    # Usta bo'yicha
    ws2 = wb.create_sheet("Ustalar bo'yicha")
    ws2.append(["Usta", "Buyurtmalar soni"])
    sorted_masters = sorted(stats["master_stats"].items(), key=lambda x: -x[1])
    for name, count in sorted_masters:
        ws2.append([sanitize_for_excel(name), count])
    
    for cell in ws2[1]:
        cell.font = Font(bold=True)
        cell.fill = hdr_fill
    if sorted_masters:
        ws2.auto_filter.ref = f"A1:B{len(sorted_masters)+1}"

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 20

    # Xizmat bo'yicha
    ws3 = wb.create_sheet("Xizmatlar bo'yicha")
    ws3.append(["Xizmat", "Buyurtmalar soni"])
    sorted_services = sorted(stats["service_stats"].items(), key=lambda x: -x[1])
    for name, count in sorted_services:
        ws3.append([sanitize_for_excel(name), count])
        
    for cell in ws3[1]:
        cell.font = Font(bold=True)
        cell.fill = hdr_fill
    if sorted_services:
        ws3.auto_filter.ref = f"A1:B{len(sorted_services)+1}"

    ws3.column_dimensions["A"].width = 50
    ws3.column_dimensions["B"].width = 20

    wb.save(file_path)
    return file_path


# ═══════════════════════════════════════════════════════════════════════════
#  NOTIFIKATSIYA YORDAMCHILARI
# ═══════════════════════════════════════════════════════════════════════════

async def notify_masters_about_new_job(bot, order, group_id: Optional[int]) -> None:
    """Guruh ustalariga yangi ish haqida xabar yuborish."""
    if not group_id:
        return

    from database import MasterGroupRepository, session_scope

    async with session_scope() as s:
        repo = MasterGroupRepository(s)
        masters = await repo.get_masters_in_group(group_id)
        group = await repo.get_by_id(group_id)

    group_name = group.name if group else "—"
    svcs = ", ".join(order.service_names_list) or "—"

    text = (
        f"🔔 <b>Yangi ish tayinlandi!</b>\n\n"
        f"<b>Mijoz:</b> {html_escape(order.client_name)}\n"
        f"<b>Model:</b> {html_escape(order.vehicle_model or '—')}\n"
        f"<b>Xizmatlar:</b> {html_escape(svcs)}\n"
        f"<b>Guruh:</b> {html_escape(group_name)}\n\n"
        f"📋 Ishni ko'rish uchun «Mening ishlarim» tugmasini bosing."
    )

    for master in masters:
        if master.telegram_id:
            try:
                await bot.send_message(master.telegram_id, text)
            except Exception:
                pass  # Agar usta botni bloklagan bo'lsa


async def send_completion_report(bot, order, master, video_file_id: str, is_video: bool, chat_id: int) -> None:
    """Ish yakunlanganda hisobot chatga yuborish."""
    if not chat_id:
        return

    group_name = "—"
    gid = order.assigned_group_id or master.group_id
    if gid:
        from database import MasterGroupRepository, session_scope
        async with session_scope() as s:
            repo = MasterGroupRepository(s)
            group_obj = await repo.get_by_id(gid)
            if group_obj:
                group_name = group_obj.name

    svcs = "\n".join(f"🔸 {x}" for x in order.service_names_list) or "—"
    txt = (
        f"✅ <b>YANGI ISH YAKUNLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🏢 <b>Bajaruvchi:</b> {html_escape(group_name)}\n"
        f"👤 <b>Mijoz:</b> {html_escape(order.client_name)}\n"
        f"🚐 <b>Mashina rusumi:</b> {html_escape(order.vehicle_model or '—')}\n"
        f"💰 <b>Umumiy summa:</b> {format_amount(order.total_amount)}\n\n"
        f"🛠 <b>Qilingan xizmatlar:</b>\n{svcs}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 <i>{datetime.now().strftime('%d.%m.%Y %H:%M')} | Lider Avtotex 555</i>"
    )

    try:
        if is_video:
            await bot.send_video(chat_id, video_file_id, caption=txt)
        else:
            await bot.send_video_note(chat_id, video_file_id)
            await bot.send_message(chat_id, txt)
    except Exception:
        pass
