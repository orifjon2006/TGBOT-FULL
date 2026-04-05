import os
import json
import gspread
import logging
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, timezone

# ═══════════════════════════════════════════════════════════════════════════
#  DIAGNOSTIKA — Google Sheets Professional Fix (Time Offset Patch bilan)
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("Diagnostic")

CREDENTIALS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def apply_time_offset_patch():
    """Google serveridan aniq vaqtni olib, driftni kompensatsiya qiladi."""
    logger.info("🕒 1. Vaqt kompensatsiyasini hisoblaymiz (Google orqali)...")
    try:
        # Google-dan vaqtni olamiz
        res = requests.head("https://www.google.com", timeout=5)
        google_date_str = res.headers.get('Date')
        if google_date_str:
            # Format: 'Sun, 05 Apr 2026 22:30:24 GMT'
            real_now = datetime.strptime(google_date_str, '%a, %d %b %Y %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            server_now = datetime.now(timezone.utc)
            delta = (real_now - server_now).total_seconds()
            
            logger.info(f"   - Server UTC: {server_now}")
            logger.info(f"   - Google UTC: {real_now}")
            logger.info(f"   - Farq:       {delta:.1f}s")
            
            # Patch qo'llash
            import google.auth._helpers
            original_utcnow = google.auth._helpers.utcnow
            def patched_utcnow():
                return original_utcnow() + timedelta(seconds=delta)
            google.auth._helpers.utcnow = patched_utcnow
            logger.info("✅ Time Offset Patch muvaffaqiyatli qo'llanildi!")
            return True
    except Exception as e:
        logger.error(f"❌ Google-dan vaqtni olishda xato: {e}")
    return False

def check_credentials():
    logger.info(f"📂 2. '{CREDENTIALS_FILE}' faylini tekshirmoqdamiz...")
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"❌ Fayl topilmadi: {CREDENTIALS_FILE}")
        return
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_data = json.load(f)
            logger.info(f"✅ Fayl o'qildi. Email: {creds_data.get('client_email')}")
            
        logger.info("🔑 3. Google API avtorizatsiyasini (Patch bilan) boshlaymiz...")
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)
        
        # Test: fayllarni ro'yxatga olish
        client.list_spreadsheet_files()
        logger.info("🚀 MUVAFFARIYAT: Google API ulanishi professional tarzda tiklandi!")
        
    except Exception as e:
        logger.error(f"❌ Avtorizatsiyada hali ham xatolik: {e}")

if __name__ == "__main__":
    print("\n--- GOOGLE SHEETS SERVER DIAGNOSTICS (FULL FIX) ---\n")
    if apply_time_offset_patch():
        check_credentials()
    else:
        print("🛑 Vaqtni olib bo'lmagani uchun diagnostika tugatildi.")
    print("\n----------------------------------------------------\n")
