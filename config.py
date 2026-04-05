"""Markaziy konfiguratsiya — barcha sozlamalar, tugma textlari va xizmat katalog ma'lumotlari."""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
#  Bot sozlamalari
# ═══════════════════════════════════════════════════════════════════════════

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
MAIN_ADMIN_TELEGRAM_ID: int = int(os.getenv("MAIN_ADMIN_TELEGRAM_ID", "0"))
COMPLETION_REPORT_CHAT_ID: int = int(os.getenv("COMPLETION_REPORT_CHAT_ID", os.getenv("WORK_REPORT_GROUP_ID", "0")))

# Google Sheets
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SHEET_SHARE_EMAIL: str = os.getenv("GOOGLE_SHEET_SHARE_EMAIL", "")

# ═══════════════════════════════════════════════════════════════════════════
#  Kompaniya ma'lumotlari
# ═══════════════════════════════════════════════════════════════════════════

COMPANY_NAME: str = os.getenv("COMPANY_NAME", "LIDER AVTOTEX 555")
COMPANY_PHONE_1: str = os.getenv("COMPANY_PHONE_1", "(95) 451 99 99")
COMPANY_PHONE_2: str = os.getenv("COMPANY_PHONE_2", "(97) 772 09 90")
COMPANY_TELEGRAM: str = os.getenv("COMPANY_TELEGRAM", "@LIDER_AVTOTEX_555")

# ═══════════════════════════════════════════════════════════════════════════
#  Fayl yo'llari
# ═══════════════════════════════════════════════════════════════════════════

TEMP_RECEIPT_DIR: str = os.getenv("TEMP_RECEIPT_DIR", "storage/temp_receipts")
TEMP_STAT_DIR: str = os.getenv("TEMP_STAT_DIR", "storage/temp_stats")

# ═══════════════════════════════════════════════════════════════════════════
#  ── BOSH MENU TUGMALARI ──
#  Faqat kundalik ish uchun kerakli tugmalar
# ═══════════════════════════════════════════════════════════════════════════

BTN_CREATE_ORDER = "📝 Buyurtma yaratish"
BTN_SEARCH_CLIENT = "🔎 Qidirish"
BTN_ACTIVE_JOBS = "🔧 Amaldagi ishlar"
BTN_STATISTICS = "📊 Statistika"
BTN_EXTRA = "⚙️ Qo'shimcha"
BTN_REFRESH = "🔄 Yangilash"

# ═══════════════════════════════════════════════════════════════════════════
#  ── QO'SHIMCHA MENU TUGMALARI ──
#  Kamroq ishlatiladigan boshqaruv tugmalari
# ═══════════════════════════════════════════════════════════════════════════

BTN_CATALOGS = "🗂 Kataloglar"
BTN_ORDER_HISTORY = "📋 Buyurtmalar tarixi"
BTN_EXPORT_EXCEL = "📤 Excel eksport"
BTN_APPROVALS = "✅ Admin so'rovlari"
BTN_MASTER_GROUPS = "👥 Usta guruhlari"

# ═══════════════════════════════════════════════════════════════════════════
#  ── LITSENZIYA TUGMALARI ──
# ═══════════════════════════════════════════════════════════════════════════
BTN_LICENSE_ADD = "📝 Litsenziya kiritish"
BTN_LICENSE_CHECK = "🔎 Litsenziya tekshirish"

# ═══════════════════════════════════════════════════════════════════════════
#  ── KATALOG TUGMALARI ──
# ═══════════════════════════════════════════════════════════════════════════

BTN_MODELS = "🚐 Modellar"
BTN_SERVICES = "🛠 Xizmatlar"
BTN_HEIGHTS = "📏 Balandliklar"
BTN_MASTERS = "👨‍🔧 Ustalar"

# ═══════════════════════════════════════════════════════════════════════════
#  ── NAVIGATSIYA TUGMALARI ──
# ═══════════════════════════════════════════════════════════════════════════

BTN_BACK = "⬅️ Ortga"
BTN_CANCEL = "❌ Bekor qilish"
BTN_MAIN_MENU = "🏠 Bosh menu"
BTN_REGISTER_SUBADMIN = "🧑‍💼 Admin bo'lib ro'yxatdan o'tish"

# ═══════════════════════════════════════════════════════════════════════════
#  Katalog nomlari map
# ═══════════════════════════════════════════════════════════════════════════

CATALOG_NAMES: dict[str, str] = {
    "models": BTN_MODELS,
    "services": BTN_SERVICES,
    "heights": BTN_HEIGHTS,
    "masters": BTN_MASTERS,
}

# ═══════════════════════════════════════════════════════════════════════════
#  XIZMATLAR DARAXTI — ko'p bosqichli tanlash uchun
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_SERVICE_TREE: dict = {
    "ustanovka_gaz": {
        "label": "Ustanovka gaz",
        "children": {
            "metan": {
                "label": "Metan",
                "children": {
                    "pok_3": {"label": "3 pok"},
                    "pok_4": {"label": "4 pok"},
                },
            },
            "propan": {
                "label": "Propan",
                "children": {
                    "pok_3": {"label": "3 pok"},
                    "pok_4": {"label": "4 pok"},
                },
            },
        },
    },
    "karona": {
        "label": "Karona",
        "children": {
            "labo": {"label": "Labo"},
            "changan": {"label": "Changan"},
            "shinerey_t30": {"label": "Shinerey T30"},
            "shinerey_t32": {"label": "Shinerey T32"},
            "kia_bongo": {"label": "Kia Bongo"},
            "kama": {"label": "Kama"},
            "shinerey_t50": {"label": "Shinerey T50"},
            "gazel_220": {"label": "Gazel 2.20"},
        },
    },
    "izotermik_furgon_sendvich": {
        "label": "Izotermik furgon sendvich",
        "children": {
            "razmer_furgon": {
                "label": "Razmer furgon",
                "children": {
                    "1_45": {"label": "1.45"},
                    "1_50": {"label": "1.50"},
                    "1_55": {"label": "1.55"},
                    "1_60": {"label": "1.60"},
                    "1_65": {"label": "1.65"},
                    "1_70": {"label": "1.70"},
                    "1_75": {"label": "1.75"},
                    "1_80": {"label": "1.80"},
                    "1_85": {"label": "1.85"},
                    "1_90": {"label": "1.90"},
                    "1_95": {"label": "1.95"},
                    "2_00": {"label": "2.00"},
                    "2_10": {"label": "2.10"},
                    "2_20": {"label": "2.20"},
                },
            },
            "qoshimcha_eshik": {"label": "Qo'shimcha eshik"},
            "sendvich_7_5_sm": {"label": "Sendvich 7.5 sm"},
            "sendvich_50_sm": {"label": "Sendvich 50 sm"},
            "karkas_nerj_2_mm": {"label": "Karkas nerj 2 mm"},
            "pol_nerj": {"label": "Pol nerj"},
            "pol_rifleniy": {"label": "Pol rifleniy"},
        },
    },
    "bortli_tentli_furgon": {
        "label": "Bortli tentli furgon",
        "children": {
            "razmer_furgon": {
                "label": "Razmer furgon",
                "children": {
                    "1_45": {"label": "1.45"},
                    "1_50": {"label": "1.50"},
                    "1_55": {"label": "1.55"},
                    "1_60": {"label": "1.60"},
                    "1_65": {"label": "1.65"},
                    "1_70": {"label": "1.70"},
                    "1_75": {"label": "1.75"},
                    "1_80": {"label": "1.80"},
                    "1_85": {"label": "1.85"},
                    "1_90": {"label": "1.90"},
                    "1_95": {"label": "1.95"},
                    "2_00": {"label": "2.00"},
                    "2_10": {"label": "2.10"},
                    "2_20": {"label": "2.20"},
                },
            },
            "tent_reklama_bilan": {"label": "Tent reklama bilan"},
            "potolok_orgalit": {"label": "Potolok orgalit"},
            "potolok_fanera": {"label": "Potolok fanera"},
            "pol_tunika": {"label": "Pol tunika"},
            "pol_finski": {"label": "Pol finski"},
            "chiroq_ichiga": {"label": "Chiroq ichiga"},
            "pol_fanera_8_mm": {"label": "Pol fanera 8 mm"},
            "fanera_guli": {"label": "Fanera guli"},
        },
    },
    "bortli_tentli_klapan_damkrat": {
        "label": "Bortli tentli klapan damkrat",
        "children": {
            "razmer_furgon": {
                "label": "Razmer furgon",
                "children": {
                    "1_45": {"label": "1.45"},
                    "1_50": {"label": "1.50"},
                    "1_55": {"label": "1.55"},
                    "1_60": {"label": "1.60"},
                    "1_65": {"label": "1.65"},
                    "1_70": {"label": "1.70"},
                    "1_75": {"label": "1.75"},
                    "1_80": {"label": "1.80"},
                    "1_85": {"label": "1.85"},
                    "1_90": {"label": "1.90"},
                    "1_95": {"label": "1.95"},
                    "2_00": {"label": "2.00"},
                    "2_10": {"label": "2.10"},
                    "2_20": {"label": "2.20"},
                },
            },
            "tent_reklama_bilan": {"label": "Tent reklama bilan"},
            "potolok_orgalit": {"label": "Potolok orgalit"},
            "potolok_fanera": {"label": "Potolok fanera"},
            "pol_tunika": {"label": "Pol tunika"},
            "pol_finski": {"label": "Pol finski"},
            "chiroq_ichiga": {"label": "Chiroq ichiga"},
            "pol_fanera_8_mm": {"label": "Pol fanera 8 mm"},
            "fanera_guli": {"label": "Fanera guli"},
        },
    },
    "shumka": {
        "label": "Shumka",
        "children": {
            "ikki_eshik": {"label": "2 ta eshik"},
            "pol_va_yoni": {"label": "Pol va yoni"},
        },
    },
    "gabarit_chiroq": {
        "label": "Gabarit chiroq",
        "children": {
            "proyektor": {"label": "Proyektor"},
            "gabarit_chiroq_yon": {"label": "Gabarit chiroq yon"},
            "karona_chiroq": {"label": "Karona chiroq"},
        },
    },
    "ressor_usileniya": {
        "label": "Ressor usileniya",
        "children": {
            "ressor_korenoy": {"label": "Ressor korenoy"},
            "ressor_qilich": {"label": "Ressor qilich"},
            "podushka_kamaz": {"label": "Podushka Kamaz"},
            "tuya_damas": {"label": "Tuya Damas"},
            "stremyanka_bolt": {"label": "Stremyanka bolt"},
        },
    },
    "video_registrator": {
        "label": "Video registrator",
        "children": {
            "lenovo": {"label": "Lenovo"},
            "teyes": {"label": "Teyes"},
            "unistar": {"label": "Unistar"},
            "unistar_077": {"label": "Unistar 077"},
        },
    },
    "bokovoy_oyna": {
        "label": "Bokovoy oyna",
        "children": {
            "xitoy_original_chiroq": {"label": "Xitoy original chiroq"},
            "xitoy_chiroqsiz": {"label": "Xitoy chiroqsiz"},
            "bokovoy_t30": {"label": "Bokovoy T30"},
        },
    },
    "tunuka_obshivka": {
        "label": "Tunuka obshivka",
        "children": {
            "0_7_komp": {"label": "0.7 komp"},
            "0_7_pol": {"label": "0.7 pol"},
            "0_7_bort": {"label": "0.7 bort"},
            "0_9_komp": {"label": "0.9 komp"},
            "0_9_bort": {"label": "0.9 bort"},
            "0_9_pol": {"label": "0.9 pol"},
        },
    },
    "yigma_tent": {
        "label": "Yigma tent",
        "children": {
            "xitoy_tent_arzon": {"label": "Xitoy tent arzon"},
            "koreya_tent_yaxshi": {"label": "Koreya tent yaxshi"},
        },
    },
    "duga_zashitnaya": {
        "label": "Duga zashitnaya",
        "children": {
            "duga_labo": {"label": "Duga Labo"},
            "shinerey_t30": {"label": "Shinerey T30"},
            "shinerey_t50": {"label": "Shinerey T50"},
            "labo_nerj": {"label": "Labo nerj"},
            "kia_bongo": {"label": "Kia Bongo"},
            "changan": {"label": "Changan"},
        },
    },
    "yashik_instrument": {
        "label": "Yashik instrument",
        "children": {
            "labo": {"label": "Labo"},
            "t30": {"label": "T30"},
            "t32": {"label": "T32"},
            "t50": {"label": "T50"},
            "kia_bongo": {"label": "Kia Bongo"},
            "changan": {"label": "Changan"},
        },
    },
    "bar": {
        "label": "Bar",
        "children": {
            "malibu_original": {"label": "Malibu original"},
            "oddiy_bar": {"label": "Oddiy bar"},
            "malibu_arzon": {"label": "Malibu arzon"},
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  ODDIY XIZMATLAR — bir bosishda qo'shiladigan
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_SIMPLE_SERVICES: list[dict[str, str]] = [
    {"key": "ressor", "label": "Ressor"},
    {"key": "chexol", "label": "Chexol"},
    {"key": "alyukabond_furgon", "label": "Alyukabond furgon"},
    {"key": "linolyum", "label": "Linolyum"},
    {"key": "nikel_bryzgovik", "label": "Nikel bryzgovik"},
    {"key": "pol_finski", "label": "Pol finski"},
    {"key": "pol_nerj", "label": "Pol nerj"},
    {"key": "rama_usileniy", "label": "Rama usileniy"},
    {"key": "alkafan_ichi", "label": "Alkafan ichi"},
    {"key": "led_chiroq_labo", "label": "Led chiroq Labo"},
    {"key": "nomer_nikel", "label": "Nomer nikel"},
    {"key": "kryuchok_bolt_ichiga", "label": "Kryuchok bolt ichiga"},
    {"key": "zapasqa_bolt", "label": "Zapasqa bolt"},
    {"key": "pol_fanera", "label": "Pol fanera"},
    {"key": "pol_pukak", "label": "Pol pukak"},
    {"key": "karkas_nerjaveyka", "label": "Karkas nerjaveyka"},
    {"key": "isuzu", "label": "Isuzu"},
    {"key": "fanera_obshivka_8_mm", "label": "Fanera obshivka 8 mm"},
    {"key": "fanera_obshivka_guli", "label": "Fanera obshivka guli"},
    {"key": "pukak_3_sm", "label": "Pukak 3 sm"},
    {"key": "led_chiroq_osvesheniya", "label": "Led chiroq osvesheniya"},
    {"key": "pol_yasaladi", "label": "Pol yasaladi"},
    {"key": "orqa_eshik_mol_tashishga", "label": "Orqa eshik mol tashishga"},
    {"key": "ichki_qism_2_etazh_120_80", "label": "Ichki qism 2 etazh 120/80"},
    {"key": "tom_qismi_tent", "label": "Tom qismi tent"},
    {"key": "orqasi_klapan_tent", "label": "Orqasi klapan tent"},
    {"key": "orqa_eshikli_furgon", "label": "Orqa eshikli furgon"},
    {"key": "bakavoy_eshik", "label": "Bakavoy eshik"},
    {"key": "tunuka_obshivka_0_9_alkafan", "label": "Tunuka obshivka 0.9 alkafan"},
    {"key": "ressor_kia", "label": "Ressor Kia"},
    {"key": "bortli_tentli", "label": "Bortli tentli"},
    {"key": "pol_tunika", "label": "Pol tunika"},
    {"key": "gaz_zashita_t30", "label": "Gaz zashita T30"},
    {"key": "rezinka_pol_labo", "label": "Rezinka pol Labo"},
    {"key": "balon_13", "label": "Balon 13"},
    {"key": "rezinka_pol_shinerey_t30", "label": "Rezinka pol Shinerey T30"},
    {"key": "ichi_nerj_30_sm_fanera", "label": "Ichi nerj 30 sm fanera"},
    {"key": "lazer_kesish_2_5_mm", "label": "Lazer kesish 2.5 mm"},
    {"key": "listogib_xizmati", "label": "Listogib xizmati"},
    {"key": "bortli_tentli_klapan", "label": "Bortli tentli klapan"},
    {"key": "fanera_obshivka_6_mm", "label": "Fanera obshivka 6 mm"},
    {"key": "oldi_fortochka_30_50", "label": "Oldi fortochka 30/50"},
    {"key": "zamena_uplotnitel_komp", "label": "Zamena uplotnitel komp"},
    {"key": "zamena_dver_komp", "label": "Zamena dver komp"},
    {"key": "pokraska_detali", "label": "Pokraska detali"},
    {"key": "svarochniy_raboti", "label": "Svarochniy raboti"},
    {"key": "germetika", "label": "Germetika"},
    {"key": "ichki_burchak_potolok_nerj", "label": "Ichki burchak potolok nerj"},
    {"key": "ressor_changan", "label": "Ressor Changan"},
    {"key": "ref_agregat_xitoy_minus_5", "label": "Ref agregat Xitoy -5"},
    {"key": "kia_bongo_isuzu_furgon", "label": "Kia Bongo Isuzu furgon"},
    {"key": "eshik_petlya_3_tali", "label": "Eshik petlya 3 tali"},
    {"key": "nerjaveyka_obshivka_0_9_bort", "label": "Nerjaveyka obshivka 0.9 bort"},
    {"key": "zamena_tent_seriy", "label": "Zamena tent seriy"},
    {"key": "zamena_orgalit", "label": "Zamena orgalit"},
    {"key": "namat_tent_uchun", "label": "Namat tent uchun"},
    {"key": "rezina_uplotnitel", "label": "Rezina uplotnitel"},
    {"key": "potolok_karkas_tentli", "label": "Potolok karkas tentli"},
    {"key": "karkas_bir_tomonlama_fanera", "label": "Karkas bir tomonlama fanera"},
    {"key": "rul_chexol_labo_tikiladI", "label": "Rul chexol Labo tikiladi"},
    {"key": "qoshimcha_eshik", "label": "Qo'shimcha eshik"},
    {"key": "karkas_orgalit_polniy", "label": "Karkas orgalit polniy"},
    {"key": "parog_shinerey_t30", "label": "Parog Shinerey T30"},
    {"key": "oldi_fortochka_30_55_ichi", "label": "Oldi fortochka 30/55 ichi"},
    {"key": "ref_agregat_xitoy_minus_10", "label": "Ref agregat Xitoy -10"},
    {"key": "rul_chexol_tikiladI", "label": "Rul chexol tikiladi"},
    {"key": "porog_shinerey_t30", "label": "Porog Shinerey T30"},
    {"key": "razvodka_ichki_patlok", "label": "Razvodka ichki patlok"},
    {"key": "patlok_chiroq_2", "label": "Patlok chiroq 2"},
    {"key": "temir_qoyish", "label": "Temir qo'yish"},
    {"key": "fortochka_eshik_2_sht", "label": "Fortochka eshik 2 sht"},
    {"key": "yon_bort_ochiladi_ichidan", "label": "Yon bort ochiladi ichidan"},
    {"key": "potolok_karkas_arkali", "label": "Potolok karkas arkali"},
    {"key": "pol_rifleniy", "label": "Pol rifleniy"},
    {"key": "patlok_fanera_6_mm", "label": "Patlok fanera 6 mm"},
    {"key": "patlok_chiroq", "label": "Patlok chiroq"},
    {"key": "shopka_tom", "label": "Shopka tom"},
    {"key": "tuya_podushka", "label": "Tuya podushka"},
]

# ═══════════════════════════════════════════════════════════════════════════
#  FURGON BALANDLIKLARI
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_VAN_HEIGHTS: list[dict[str, str]] = [
    {"key": "1_45", "label": "1.45"},
    {"key": "1_50", "label": "1.50"},
    {"key": "1_55", "label": "1.55"},
    {"key": "1_60", "label": "1.60"},
    {"key": "1_65", "label": "1.65"},
    {"key": "1_70", "label": "1.70"},
    {"key": "1_75", "label": "1.75"},
    {"key": "1_80", "label": "1.80"},
    {"key": "1_85", "label": "1.85"},
    {"key": "1_90", "label": "1.90"},
    {"key": "1_95", "label": "1.95"},
    {"key": "2_00", "label": "2.00"},
    {"key": "2_10", "label": "2.10"},
    {"key": "2_20", "label": "2.20"},
]
