import os
import json
import gspread
import logging
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone
import requests

# ═══════════════════════════════════════════════════════════════════════════
#  DIAGNOSTIKA — Server vaqti va Google API ulanishini tekshirish
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("Diagnostic")

CREDENTIALS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def apply_time_offset_patch():
    """Server vaqti va haqiqiy vaqt farqini (drift) hisoblab, google-auth kutubxonasini patch qiladi."""
    logger.info("🕒 1. Vaqt kompensatsiyasini hisoblaymiz...")
    try:
        response = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=5)
        if response.status_code == 200:
            real_now_str = response.json()['datetime']
            real_now = datetime.fromisoformat(real_now_str.replace('Z', '+00:00'))
            server_now = datetime.now(timezone.utc)
            delta = real_now - server_now
            
            logger.info(f"   - Server UTC: {server_now}")
            logger.info(f"   - Real UTC:   {real_now}")
            logger.info(f"   - Farq:       {delta.total_seconds():.1f}s")
            
            # Patch qo'llash
            import google.auth._helpers
            original_utcnow = google.auth._helpers.utcnow
            def patched_utcnow():
                return original_utcnow() + timedelta(seconds=delta.total_seconds())
            google.auth._helpers.utcnow = patched_utcnow
            logger.info("✅ Time Offset Patch qo'llanildi!")
            return True
    except Exception as e:
        logger.error(f"❌ Vaqtni olishda xato: {e}")
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
    print("\n--- GOOGLE SHEETS SERVER DIAGNOSTICS (WITH PATCH) ---\n")
    if apply_time_offset_patch():
        check_credentials()
    else:
        print("🛑 Vaqtni internetdan olib bo'lmagani uchun diagnostika tugatildi.")
    print("\n-----------------------------------------------------\n")
