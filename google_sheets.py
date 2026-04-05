import os
import json
import logging
from typing import List, Optional
from datetime import datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials
import google.auth._helpers  # Monkeypatching uchun kerak
import requests
import config

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
#  🕒 TIME OFFSET COMPENSATOR — Server vaqti xatoligini to'g'rilash
# ═══════════════════════════════════════════════════════════════════════════

def apply_time_offset_patch():
    """Google serveridan aniq vaqtni olib, driftni kompensatsiya qiladi."""
    try:
        # 1. Google-dan vaqtni olamiz (u har doim to'g'ri UTC vaqt beradi)
        res = requests.head("https://www.google.com", timeout=5)
        google_date_str = res.headers.get('Date')
        if google_date_str:
            # Format: 'Mon, 06 Apr 2026 22:30:24 GMT'
            real_now = datetime.strptime(google_date_str, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            server_now = datetime.now(timezone.utc)
            delta = (real_now - server_now).total_seconds()
            
            # 30 soniyalik zaxira (buffer) qo'shamiz - bu Google "kelajakdagi token" deb rad etmasligi uchun
            adjusted_delta = delta - 30
            
            logger.info(f"🕒 [TimeCompensator] Offset: {delta:.1f}s. Adjusted: {adjusted_delta:.1f}s. Patch qo'llanilmoqda...")
            import google.auth._helpers
            original_utcnow = google.auth._helpers.utcnow
            def patched_utcnow():
                return original_utcnow() + timedelta(seconds=adjusted_delta)
            google.auth._helpers.utcnow = patched_utcnow
            logger.info("✅ [TimeCompensator] Google Auth kutubxonasi agressiv offset bilan yamoqlandi.")
    except Exception as e:
        logger.warning(f"⚠️ [TimeCompensator] Vaqtni olishda xato: {e}")

# Modul yuklanganda patchni qo'llaymiz
apply_time_offset_patch()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_TITLE = "Bot Buyurtmalari (Zayavkalar)"

class GoogleSheetsManager:
    def __init__(self):
        self.credentials_path = CREDENTIALS_FILE
        self.client: Optional[gspread.Client] = None
        self.sheet_id = config.GOOGLE_SHEET_ID
        self.share_email = config.GOOGLE_SHEET_SHARE_EMAIL

    def get_client(self) -> Optional[gspread.Client]:
        if self.client:
            return self.client
            
        if not os.path.exists(self.credentials_path):
            logger.error("🛑 [GoogleSheets] credentials.json fayli topilmadi!")
            return None

        try:
            credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=SCOPES
            )
            self.client = gspread.authorize(credentials)
            return self.client
        except Exception as e:
            if "Invalid JWT Signature" in str(e):
                logger.error("🛑 [GoogleSheets] VAQT XATOLIGI! Server vaqti noto'g'ri. JWT Signature rad etildi.")
            else:
                logger.error(f"🛑 [GoogleSheets] API avtorizatsiyada xatolik: {e}", exc_info=True)
            return None

    def get_or_create_spreadsheet(self) -> Optional[gspread.Spreadsheet]:
        client = self.get_client()
        if not client:
            return None

        # 1. ID orqali ochish (Eng ishonchli usul)
        if self.sheet_id:
            try:
                sh = client.open_by_key(self.sheet_id)
                logger.info(f"✅ [GoogleSheets] Jadval ID orqali ochildi: {self.sheet_id}")
                return sh
            except Exception as e:
                logger.error(f"🛑 [GoogleSheets] ID orqali ochishda xato ({self.sheet_id}): {e}")

        # 2. Nomi bo'yicha qidirib ko'ramiz
        try:
            sh = client.open(SPREADSHEET_TITLE)
            return sh
        except gspread.exceptions.SpreadsheetNotFound:
            logger.info(f"Yangi jadval yaratilmoqda: '{SPREADSHEET_TITLE}'...")
            try:
                sh = client.create(SPREADSHEET_TITLE)
                
                # Foydalanuvchiga ruxsat berish (Email orqali)
                if self.share_email:
                    try:
                        sh.share(self.share_email, perm_type='user', role='writer', notify=True)
                        logger.info(f"✅ Jadval '{self.share_email}' bilan ulashildi.")
                    except Exception as share_err:
                        logger.warning(f"⚠️ Share qilishda xato: {share_err}")

                # Birinchi listni chiroyli qilib sozlaymiz
                sheet = sh.get_worksheet(0)
                sheet.update_title("Buyurtmalar")
                
                header = ["Tartib Raqami", "Mijoz Ismi", "Xizmatlar", "Umumiy Summa", "Qabul qilingan sana", "Ustalar", "Tugallangan sana"]
                sheet.append_row(header)
                sheet.format("A1:G1", {
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                    "backgroundColor": {"red": 0.1, "green": 0.5, "blue": 0.8},
                    "horizontalAlignment": "CENTER"
                })
                logger.info(f"✅ Yangi jadval yaratildi: {sh.url}")
                return sh
            except Exception as e:
                logger.error(f"🛑 [GoogleSheets] Jadval yaratib bo'lmadi: {e}", exc_info=True)
                return None

    def append_order(self, order_data: List[str]) -> bool:
        """Yangi buyurtmani oxirgi qatorga yozib qo'yadi va 10 yillik tajribali dizaynni qoplaydi."""
        sh = self.get_or_create_spreadsheet()
        if not sh:
            return False

        try:
            try:
                sheet = sh.worksheet("Buyurtmalar")
            except gspread.exceptions.WorksheetNotFound:
                sheet = sh.get_worksheet(0)
                
            # Ma'lumotlarni yozish (agar birinchi qator bo'sh bo'lsa sarlavha ham qo'shamiz)
            first_val = sheet.acell('A1').value
            if not first_val:
                header = ["Tartib Raqami", "Mijoz Ismi", "Xizmatlar", "Umumiy Summa", "Qabul qilingan sana", "Ustalar", "Tugallangan sana"]
                sheet.append_row(header)
                sheet.format("A1:G1", {
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                    "backgroundColor": {"red": 0.1, "green": 0.5, "blue": 0.8},
                    "horizontalAlignment": "CENTER"
                })
                
            res = sheet.append_row(order_data, value_input_option='USER_ENTERED')
            logger.info(f"✅ [GoogleSheets] Buyurtma yozildi: {order_data[0]}")
            
            # 🎨 PROFESSIONAL DIZAYNNI QO'LLASH (Shu qator va umumiy ustunlar uchun)
            self._apply_professional_formatting(sh, sheet, res)
            
            return True
            
        except Exception as e:
            logger.error(f"🛑 [GoogleSheets] Qatorni qo'shish va bezashda xatolik: {e}", exc_info=True)
            return False

    def _apply_professional_formatting(self, sh: gspread.Spreadsheet, sheet: gspread.Worksheet, append_res: dict) -> None:
        """Kiritilgan yangi qatorga va ustunlarga o'ta chiroyli professional dizayn beradi."""
        try:
            # Append qilingan qator raqamini topamiz (masalan 'Buyurtmalar!A5:F5' -> 5)
            updated_range = append_res.get('updates', {}).get('updatedRange', '')
            if not updated_range:
                return
            
            row_num_str = ''.join(filter(str.isdigit, updated_range.split('!')[1].split(':')[0]))
            if not row_num_str:
                return
            row_idx = int(row_num_str) - 1  # 0-indexed API uchun

            requests = [
                # 1. Barcha yoziladigan qator uchun umumiy o'rta (Middle) tekislash va chegaralar
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": 7},
                        "cell": {
                            "userEnteredFormat": {
                                "verticalAlignment": "MIDDLE",
                                "wrapStrategy": "WRAP",
                                "borders": {
                                    "bottom": {"style": "SOLID", "width": 1, "color": {"red": 0.9, "green": 0.9, "blue": 0.9}}
                                }
                            }
                        },
                        "fields": "userEnteredFormat(verticalAlignment, wrapStrategy, borders)"
                    }
                },
                # 2. Buyurtma ID ustuni (A) - Markaz, Qalinroq (Bold), Kulrang
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER", "textFormat": {"bold": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # 3. Mijoz Ismi ustuni (B) - Chapga, To'q ko'k, Kattaroq shrift
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 1, "endColumnIndex": 2},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT", "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 0.1, "green": 0.25, "blue": 0.45}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # 4. Xizmatlar (C) - Chapga, matn qatorga bo'linadi (Wrap)
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 2, "endColumnIndex": 3},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT", "textFormat": {"foregroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # 5. Summa (D) - O'ngga, Qalin, To'q yashil
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 3, "endColumnIndex": 4},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "RIGHT", "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 0.1, "green": 0.6, "blue": 0.2}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # 6. Sana (E) - O'ngga, Qiyalik (Italic), Kulrang
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 4, "endColumnIndex": 5},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "RIGHT", "textFormat": {"italic": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # 7. Ustalar (F) - Markaziy o'rta kattalikdagi ismlar
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 5, "endColumnIndex": 6},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER", "textFormat": {"bold": True, "foregroundColor": {"red": 0.1, "green": 0.3, "blue": 0.4}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # 8. Tugallangan Sana (G) - Markaz, Yashil rangda yoxud Kulrang
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 6, "endColumnIndex": 7},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER", "textFormat": {"bold": True, "foregroundColor": {"red": 0.1, "green": 0.5, "blue": 0.3}}}},
                        "fields": "userEnteredFormat(horizontalAlignment, textFormat)"
                    }
                },
                # UCHUNLAR KENGAYTMASI (Har doim zo'r ko'rinishi uchun ustunlarni qat'iy o'lchamlash)
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                        "properties": {"pixelSize": 90},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
                        "properties": {"pixelSize": 180},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
                        "properties": {"pixelSize": 350},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4},
                        "properties": {"pixelSize": 140},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 5},
                        "properties": {"pixelSize": 150},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 5, "endIndex": 6},
                        "properties": {"pixelSize": 200},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet.id, "dimension": "COLUMNS", "startIndex": 6, "endIndex": 7},
                        "properties": {"pixelSize": 150},
                        "fields": "pixelSize"
                    }
                }
            ]
            
            sh.batch_update({"requests": requests})
            logger.info("🎨 Professional dizayn varaqqa qo'llanildi!")
        except Exception as e:
            logger.warning(f"Dizayn berishda kichik xatolik (ma'lumot yozilgan, dizaynda xato): {e}")

    def complete_order(self, order_id: str, completion_date: str) -> bool:
        """Buyurtma yakunlanganida uning faqat sanasini Google Sheetsda topib yangilaydi (Ustalar ro'yxati saqlab qolinadi)."""
        sh = self.get_or_create_spreadsheet()
        if not sh:
            return False

        try:
            try:
                sheet = sh.worksheet("Buyurtmalar")
            except gspread.exceptions.WorksheetNotFound:
                sheet = sh.get_worksheet(0)
            
            # A ustunida (1-chi ustun) Order ID ni qidiramiz
            cell = sheet.find(str(order_id), in_column=1)
            if cell:
                # FAQAT 7-chi ustun (Tugallangan sana, ya'ni G ustun) ga sana yozib qo'yamiz
                sheet.update_acell(f"G{cell.row}", completion_date)
                logger.info(f"✅ [GoogleSheets] Buyurtma tugatildi (ID: {order_id}) - Sana qo'yildi.")
                return True
            else:
                logger.warning(f"⚠️ [GoogleSheets] ID bo'yicha {order_id} topilmadi! Sanani update qilib bo'lmadi.")
                return False
        except Exception as e:
            logger.error(f"🛑 [GoogleSheets] Tugallashni yozishda xato: {e}", exc_info=True)
            return False

def append_order_to_sheet(order_data: List[str]) -> bool:
    """Oson ishlatish uchun sinxron wrapper funksiya."""
    manager = GoogleSheetsManager()
    return manager.append_order(order_data)

def complete_order_in_sheet(order_id: str, completion_date: str) -> bool:
    """Oson ishlatish uchun sinxron wrapper funksiya."""
    manager = GoogleSheetsManager()
    return manager.complete_order(order_id, completion_date)

class LicenseSheetsManager:
    """Litsenziyalar bilan alohida ishlash uchun manager."""
    def append_license(self, license_data: List[str]) -> bool:
        manager = GoogleSheetsManager()
        sh = manager.get_or_create_spreadsheet()
        if not sh:
            return False

        try:
            try:
                sheet = sh.worksheet("Litsenziyalar")
            except gspread.exceptions.WorksheetNotFound:
                sheet = sh.add_worksheet(title="Litsenziyalar", rows="1000", cols="6")
                headers = ["VIN Kod", "Mijoz Ismi", "Telefon Raqam", "Topshirilgan Sana", "Tayyor bo'lish Sanasi", "Zakaz №"]
                sheet.append_row(headers)
                sheet.format("A1:F1", {
                    "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.8},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                    "horizontalAlignment": "CENTER"
                })

            sheet.append_row(license_data)
            row_idx = len(sheet.get_all_values())
            sheet.format(f"A{row_idx}:F{row_idx}", {
                "horizontalAlignment": "CENTER", "textFormat": {"bold": True}
            })
            logger.info("✅ [GoogleSheets] Yangi litsenziya muvaffaqiyatli qo'shildi.")
            return True
        except Exception as e:
            logger.error(f"🛑 [GoogleSheets] Litsenziya yozishda xato: {e}", exc_info=True)
            return False

def append_license_to_sheet(license_data: List[str]) -> bool:
    """Litsenziya obyekti yaratilganda sheetsga jo'natuvchi wrapper."""
    return LicenseSheetsManager().append_license(license_data)



