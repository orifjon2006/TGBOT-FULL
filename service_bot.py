"""
Alohida Xizmat ko'rsatish va Buyurtma (Zayavka) qabul qilish boti.
Ushbu bot to'liq o'z bazasiga ega bo'lgan holda mustaqil ishlaydi,
Mijozlar buyurtmalari to'g'ridan-to'g'ri ko'rsatilgan guruhga tushadi.
"""

import asyncio
import logging
import sqlite3
import aiosqlite
from datetime import datetime

from google_sheets import append_order_to_sheet

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ====================================================
# SOZLAMALAR - Shu yerlarni o'zingiznikiga o'zgartiring
# ====================================================
BOT_TOKEN = "SIZNING_YANGI_BOT_TOKEN_INGIZ"
ADMIN_GROUP_ID = -1000000000000  # Zayavkalar tushadigan guruh id si, masalan: -1001234567
MAIN_ADMIN_ID = 123456789        # SIZNING TELEGRAM ID INGIZ (Barcha huquqlar)

DB_NAME = "service_bot.db"

logging.basicConfig(level=logging.INFO)

# ====================================================
# BAZA (DATABASE) FUNKSIYALARI
# ====================================================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                full_name TEXT,
                phone TEXT,
                role TEXT DEFAULT 'user'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER NULL,
                name TEXT,
                FOREIGN KEY(parent_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT,
                description TEXT,
                price INTEGER,
                FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_id TEXT,  -- bu yerda cart_ids larni saqlaymiz TEXT qilib
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER,
                service_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vin_code TEXT UNIQUE,
                client_name TEXT,
                client_phone TEXT,
                applied_date TEXT,
                issuance_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# User Baza Metodlari
async def add_or_update_user(telegram_id, full_name, phone):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            user = await cursor.fetchone()
        if user:
            await db.execute("UPDATE users SET full_name = ?, phone = ? WHERE telegram_id = ?", (full_name, phone, telegram_id))
        else:
            role = 'admin' if telegram_id == MAIN_ADMIN_ID else 'user'
            await db.execute("INSERT INTO users (telegram_id, full_name, phone, role) VALUES (?, ?, ?, ?)",
                             (telegram_id, full_name, phone, role))
        await db.commit()

async def get_user(telegram_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, telegram_id, full_name, phone, role FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "telegram_id": row[1], "full_name": row[2], "phone": row[3], "role": row[4]}
            return None

# Kategoriya Metodlari
async def add_category(name, parent_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
        await db.commit()

async def get_categories(parent_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        if parent_id is None:
            async with db.execute("SELECT id, name FROM categories WHERE parent_id IS NULL") as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,)) as cursor:
                return await cursor.fetchall()

async def get_category(cat_id):
    async with aiosqlite.connect(DB_NAME) as db:
         async with db.execute("SELECT id, name, parent_id FROM categories WHERE id = ?", (cat_id,)) as cursor:
            return await cursor.fetchone()

# Xizmat Metodlari
async def add_service(category_id, name, description, price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO services (category_id, name, description, price) VALUES (?, ?, ?, ?)",
                         (category_id, name, description, price))
        await db.commit()

async def get_services(category_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, description, price FROM services WHERE category_id = ?", (category_id,)) as cursor:
            return await cursor.fetchall()

async def get_service(service_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, category_id, name, description, price FROM services WHERE id = ?", (service_id,)) as cursor:
            return await cursor.fetchone()


# ---- SAVATCHA METODLARI ----
async def toggle_cart_item(user_id, service_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM cart_items WHERE user_id = ? AND service_id = ?", (user_id, service_id)) as cursor:
            exists = await cursor.fetchone()
        
        if exists:
            await db.execute("DELETE FROM cart_items WHERE user_id = ? AND service_id = ?", (user_id, service_id))
        else:
            await db.execute("INSERT INTO cart_items (user_id, service_id) VALUES (?, ?)", (user_id, service_id))
        await db.commit()

async def get_user_cart(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price 
            FROM cart_items c
            JOIN services s ON c.service_id = s.id
            WHERE c.user_id = ?
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2]} for r in rows]

async def clear_cart(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()


# ---- LITSENZIYA METODLARI ----
async def add_license(vin_code, client_name, client_phone, applied_date, issuance_date):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO licenses (vin_code, client_name, client_phone, applied_date, issuance_date) VALUES (?, ?, ?, ?, ?)",
                (vin_code, client_name, client_phone, applied_date, issuance_date)
            )
            await db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

async def get_license_by_vin(vin_code):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT vin_code, client_name, client_phone, applied_date, issuance_date FROM licenses WHERE vin_code = ?",
            (vin_code,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"vin": row[0], "name": row[1], "phone": row[2], "applied": row[3], "issuance": row[4]}
            return None


# ====================================================
# FSM STATES (Holatlar)
# ====================================================

class RegisterState(StatesGroup):
    full_name = State()
    phone = State()

class AdminCategoryState(StatesGroup):
    name = State()

class AdminServiceState(StatesGroup):
    name = State()
    description = State()
    price = State()

class LicenseAddState(StatesGroup):
    vin = State()
    client_name = State()
    client_phone = State()

class LicenseSearchState(StatesGroup):
    vin = State()

# ====================================================
# ROUTER & HANDLERS (Foydalanuvchi qismi)
# ====================================================
router = Router()

def main_menu_kb(is_admin=False):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🛒 Xizmatlar / Buyurtma berish")
    builder.button(text="📋 Qo'shimcha xizmatlar")
    if is_admin:
        builder.button(text="⚙️ Admin Panel")
    builder.adjust(2, 1) if is_admin else builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def extra_services_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📝 Litsenziya kiritish")
    builder.button(text="🔎 Litsenziya tekshirish")
    builder.button(text="🔙 Ortga qayish")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    # Avtomatik Main admin rolni berish
    if message.from_user.id == MAIN_ADMIN_ID and not user:
        await add_or_update_user(message.from_user.id, message.from_user.full_name, "Admin")
        user = await get_user(message.from_user.id)

    if not user or not user.get("phone"):
        await message.answer("Assalomu alaykum! Xizmatimizdan foydalanish uchun ro'yxatdan o'ting.\n\nIltimos, Ism-familiyangizni kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.full_name)
    else:
        is_admin = user["role"] == "admin" or message.from_user.id == MAIN_ADMIN_ID
        await message.answer("Xush kelibsiz! Asosiy menyudasiz.", reply_markup=main_menu_kb(is_admin))

@router.message(RegisterState.full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    builder = ReplyKeyboardBuilder()
    builder.button(text="📞 Telefon raqamni yuborish", request_contact=True)
    await message.answer("Ajoyib! Endi telefon raqamingizni yuboring (tugmani bosib yoki yozib):", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(RegisterState.phone)

@router.message(RegisterState.phone)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    full_name = data.get("full_name")
    
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text
        
    await add_or_update_user(message.from_user.id, full_name, phone)
    await state.clear()
    
    is_admin = message.from_user.id == MAIN_ADMIN_ID
    await message.answer("Siz muvaffaqiyatli ro'yxatdan o'tdingiz! Menyudan foydalanishingiz mumkin.", reply_markup=main_menu_kb(is_admin))

# --- XIZMATLARNI KO'RISH VA BUYURTMA QILISH ---

async def generate_catalog_kb(user_id, parent_id=None):
    builder = InlineKeyboardBuilder()
    
    cart = await get_user_cart(user_id)
    cart_ids = [item["id"] for item in cart]
    
    categories = await get_categories(parent_id)
    for cat in categories:
        builder.button(text=f"📂 {cat[1]}", callback_data=f"user_cat_{cat[0]}")
        
    if parent_id is not None:
        services = await get_services(parent_id)
        for srv in services:
            # Agar savatchada bor bo'lsa ptichka qo'yiladi
            mark = "✅" if srv[0] in cart_ids else "🛠"
            builder.button(text=f"{mark} {srv[1]}", callback_data=f"user_tg_{srv[0]}_{parent_id}")
            
    builder.adjust(1)
    
    # Orqaga tugmasi logikasi
    if parent_id is not None:
        cat_info = await get_category(parent_id)
        if cat_info and cat_info[2] is not None: 
            builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"user_cat_{cat_info[2]}"))
        else: 
            builder.row(InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="user_cat_main"))
            
    # Pastdagi doimiy Savatcha tugmasi        
    if cart_ids:
        builder.row(InlineKeyboardButton(text=f"🛒 Hisoblash va Rasmiylashtirish ({len(cart)}ta)", callback_data="cart_view"))
            
    return builder.as_markup()

@router.message(F.text == "🛒 Xizmatlar / Buyurtma berish")
async def show_main_catalog(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return
    kb = await generate_catalog_kb(user["id"], parent_id=None)
    await message.answer("Siz bir necha xizmatni bittada bemalol tanlab yuborishingiz mumkin. Kategoriya tanlang:", reply_markup=kb)

@router.callback_query(F.data == "user_cat_main")
async def back_to_main_catalog(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    kb = await generate_catalog_kb(user["id"], parent_id=None)
    await call.message.edit_text("Kategoriya tanlang:", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("user_cat_"))
async def open_category_user(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    cat_id = int(call.data.split("_")[2])
    cat_info = await get_category(cat_id)
    if not cat_info:
        await call.answer("Bo'lim topilmadi!", show_alert=True)
        return
        
    kb = await generate_catalog_kb(user["id"], parent_id=cat_id)
    await call.message.edit_text(f"📂 Bo'lim: <b>{cat_info[1]}</b>\n\nQuyidan o'zingizga kerakli xizmatlar ustiga bosing (✅):", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("user_tg_"))
async def toggle_service(call: CallbackQuery):
    parts = call.data.split("_")
    srv_id = int(parts[2])
    parent_id = int(parts[3])
    
    user = await get_user(call.from_user.id)
    # Savatga qo'shadi yoki olib tashlaydi
    await toggle_cart_item(user["id"], srv_id)
    
    kb = await generate_catalog_kb(user["id"], parent_id)
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "cart_view")
async def show_cart(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    cart = await get_user_cart(user["id"])
    if not cart:
        await call.answer("Savatcha hozircha bo'sh!", show_alert=True)
        return
        
    text = "🛒 <b>Sizning tanlovingiz:</b>\n\n"
    total = 0
    for i, item in enumerate(cart, 1):
        text += f"<b>{i}.</b> {item['name']}\n"
        total += item["price"]
        
    text += f"\n💰 <b>Jami hisoblangan summa:</b> {total:,} so'm\n\nMa'lumotlar to'g'rimi? Tasdiqlaysizmi?"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Zayavkani tasdiqlash", callback_data="cart_confirm")
    builder.button(text="🔙 Xizmatlarga qaytish", callback_data="user_cat_main")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@router.callback_query(F.data == "cart_confirm")
async def finalize_order(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    cart = await get_user_cart(user["id"])
    
    if not cart:
        await call.answer("Savatcha bo'sh!", show_alert=True)
        return
        
    total = sum(item["price"] for item in cart)
    cart_ids = ",".join(str(item["id"]) for item in cart)
    service_names = ", ".join(item["name"] for item in cart)
    
    # Bazaga yozish
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("INSERT INTO orders (user_id, service_id, status) VALUES (?, ?, 'pending')", (user["id"], cart_ids))
        await db.commit()
        order_id = cursor.lastrowid
    
    order_text = (
        f"🔔 <b>YANGI BUYURTMA (ZAYAVKA)</b>\n\n"
        f"👤 <b>Mijoz:</b> {user['full_name']}\n"
        f"📞 <b>Raqami:</b> {user['phone']}\n"
        f"🔗 <b>Username:</b> @{call.from_user.username if call.from_user.username else 'yoq'}\n\n"
        f"🛠 <b>TANLANGAN XIZMATLAR:</b>\n"
    )
    for i, item in enumerate(cart, 1):
        order_text += f"{i}. {item['name']}\n"
        
    order_text += f"\n💰 <b>UMUMIY HISOB:</b> {total:,} so'm"
    
    try:
        await call.bot.send_message(chat_id=ADMIN_GROUP_ID, text=order_text)
    except Exception as e:
        logging.error(f"Guruhga xabar yuborishda xatolik! GROUP IDni tekshiring: {e}")
        
    # Savatni tozalaymiz
    await clear_cart(user["id"])
    
    # ----- Yangi qo'shilgan qism: Google Sheets ga yozish -----
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_data = [
        str(order_id),
        user['full_name'],
        user['phone'],
        service_names,
        f"{total:,}",
        current_time
    ]
    # Asinxron tarzda Google Sheetsga yuboramiz (botni qotirib qo'ymaslik uchun)
    asyncio.create_task(asyncio.to_thread(append_order_to_sheet, order_data))
    # ----------------------------------------------------------
    
    await call.message.edit_text(
        "✅ Buyurtmangiz qabul qilindi va ma'muriyatga yuborildi!\nTez orada siz bilan bog'lanishadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Asosiy menyuga", callback_data="user_cat_main")]])
    )
    await call.answer()


# ====================================================
# ROUTER & HANDLERS (Admin qismi)
# ====================================================

@router.message(F.text == "⚙️ Admin Panel")
async def admin_panel_start(message: Message):
    user = await get_user(message.from_user.id)
    if not user or (user["role"] != "admin" and message.from_user.id != MAIN_ADMIN_ID):
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="📂 Asosiy Kategoriyalar boshqaruvi", callback_data="admin_cat_main")
    builder.button(text="➕ Yangi Asosiy Kategoriya qo'shish", callback_data="admin_add_cat_null")
    builder.adjust(1)
    
    await message.answer("👨‍💻 Admin Panelga xush kelibsiz! Menyuni tanlang:", reply_markup=builder.as_markup())


async def admin_cat_kb(parent_id=None):
    builder = InlineKeyboardBuilder()
    categories = await get_categories(parent_id)
    
    for cat in categories:
        builder.button(text=f"📂 {cat[1]}", callback_data=f"admin_view_cat_{cat[0]}")
        
    if parent_id is not None:
        services = await get_services(parent_id)
        for srv in services:
            builder.button(text=f"🛠 {srv[1]} (-)", callback_data=f"admin_view_srv_{srv[0]}")
            
    builder.adjust(1)
    
    # Qo'shish knopkalari
    builder.row(InlineKeyboardButton(text="➕ Ichki Kategoriya qo'shish", callback_data=f"admin_add_cat_{parent_id if parent_id else 'null'}"))
    if parent_id is not None:
        builder.row(InlineKeyboardButton(text="➕ XIZMAT qo'shish (shu kategoriya ichiga)", callback_data=f"admin_add_srv_{parent_id}"))

    # Orqaga
    if parent_id is not None:
        cat_info = await get_category(parent_id)
        if cat_info and cat_info[2] is not None:
            builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_view_cat_{cat_info[2]}"))
        else:
            builder.row(InlineKeyboardButton(text="🔙 Asosiy Admin menyuga", callback_data="admin_cat_main"))
            
    return builder.as_markup()

@router.callback_query(F.data == "admin_cat_main")
async def show_admin_cat_main(call: CallbackQuery):
    kb = await admin_cat_kb(parent_id=None)
    await call.message.edit_text("📂 Asosiy Kategoriyalar:", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("admin_view_cat_"))
async def open_admin_category(call: CallbackQuery):
    cat_id = int(call.data.split("_")[3])
    cat_info = await get_category(cat_id)
    kb = await admin_cat_kb(parent_id=cat_id)
    await call.message.edit_text(f"📂 Tahrirlanmoqda: <b>{cat_info[1]}</b>", reply_markup=kb)
    await call.answer()

# -- Kategoriya Qo'shish --
@router.callback_query(F.data.startswith("admin_add_cat_"))
async def process_add_cat(call: CallbackQuery, state: FSMContext):
    parent_str = call.data.split("_")[3]
    parent_id = None if parent_str == "null" else int(parent_str)
    
    await state.update_data(parent_id=parent_id)
    await call.message.answer("Yangi kategoriya nomini yozib yuboring (masalan: Shumka izolyatsiya):")
    await state.set_state(AdminCategoryState.name)
    await call.answer()

@router.message(AdminCategoryState.name)
async def process_add_cat_name(message: Message, state: FSMContext):
    data = await state.get_data()
    parent_id = data.get("parent_id")
    await add_category(message.text, parent_id)
    
    await message.answer(f"✅ Kategoriya qo'shildi: {message.text}")
    await state.clear()

# -- Xizmat Qo'shish --
@router.callback_query(F.data.startswith("admin_add_srv_"))
async def process_add_srv(call: CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[3])
    await state.update_data(category_id=cat_id)
    
    await call.message.answer("Yangi xizmat nomi nima? (masalan: 4ta Eshik shumkasi):")
    await state.set_state(AdminServiceState.name)
    await call.answer()

@router.message(AdminServiceState.name)
async def process_srv_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Xizmat haqida batafsil ma'lumot (izoh) bering:")
    await state.set_state(AdminServiceState.description)

@router.message(AdminServiceState.description)
async def process_srv_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Narxini kiriting faqat randa (masalan: 1500000 yoki 100):")
    await state.set_state(AdminServiceState.price)

@router.message(AdminServiceState.price)
async def process_srv_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.replace(" ", "").strip())
    except ValueError:
        await message.answer("Iltimos faqat son kiriting (masalan 1500000):")
        return
        
    data = await state.get_data()
    await add_service(data["category_id"], data["name"], data["description"], price)
    
    await message.answer(f"✅ Xizmat muvaffaqiyatli qo'shildi!\nNomi: {data['name']}\nNarxi: {price} so'm")
    await state.clear()


# ====================================================
# QO'SHIMCHA XIZMATLAR (LITSENZIYA)
# ====================================================

@router.message(F.text == "📋 Qo'shimcha xizmatlar")
async def show_extra_services(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📋 Qo'shimcha xizmatlar bo'limi:", reply_markup=extra_services_kb())

@router.message(F.text == "🔙 Ortga qayish")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    user = await get_user(message.from_user.id)
    is_admin = user and (user["role"] == "admin" or message.from_user.id == MAIN_ADMIN_ID)
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin))


# ---- Litsenziya Kiritish ----
@router.message(F.text == "📝 Litsenziya kiritish")
async def start_add_license(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    is_admin = user and (user["role"] == "admin" or message.from_user.id == MAIN_ADMIN_ID)
    if not is_admin:
        await message.answer("❌ Bu funksiya faqat adminlar uchun!")
        return
    await state.clear()
    await state.set_state(LicenseAddState.vin)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Bekor qilish")
    await message.answer(
        "📝 Yangi litsenziya kiritish.\n\n🔢 Avtomobil VIN kodini kiriting:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(LicenseAddState.vin)
async def lic_process_vin(message: Message, state: FSMContext):
    if message.text == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("📋 Qo'shimcha xizmatlar:", reply_markup=extra_services_kb())
        return
    vin = (message.text or "").strip().upper()
    if len(vin) < 3:
        await message.answer("❌ VIN kod juda qisqa. Qayta kiriting:")
        return
    existing = await get_license_by_vin(vin)
    if existing:
        await message.answer(
            f"⚠️ Bu VIN kodli litsenziya allaqachon mavjud!\n"
            f"📏 Tayyor bo'lishi: <b>{existing['issuance']}</b>\n\n"
            f"Boshqa VIN kiriting yoki Bekor qiling."
        )
        return
    await state.update_data(vin=vin)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Bekor qilish")
    await message.answer("👤 Mijoz ismini kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(LicenseAddState.client_name)

@router.message(LicenseAddState.client_name)
async def lic_process_name(message: Message, state: FSMContext):
    if message.text == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("📋 Qo'shimcha xizmatlar:", reply_markup=extra_services_kb())
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❌ Ism juda qisqa. Qayta kiriting:")
        return
    await state.update_data(client_name=name)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Bekor qilish")
    await message.answer("📞 Mijoz telefon raqamini kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(LicenseAddState.client_phone)

@router.message(LicenseAddState.client_phone)
async def lic_process_phone(message: Message, state: FSMContext):
    if message.text == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("📋 Qo'shimcha xizmatlar:", reply_markup=extra_services_kb())
        return
    phone = (message.text or "").strip()
    data = await state.get_data()
    vin = data["vin"]
    client_name = data["client_name"]
    
    from datetime import timedelta
    now = datetime.now()
    applied = now.strftime("%Y-%m-%d")
    issuance = (now + timedelta(days=10)).strftime("%Y-%m-%d")
    
    ok = await add_license(vin, client_name, phone, applied, issuance)
    await state.clear()
    
    if ok:
        # Google Sheets ga yuborish
        from google_sheets import append_license_to_sheet
        sheet_data = [vin, client_name, phone, applied, issuance]
        asyncio.create_task(asyncio.to_thread(append_license_to_sheet, sheet_data))
        
        await message.answer(
            f"✅ <b>Litsenziya muvaffaqiyatli ro'yxatga olindi!</b>\n\n"
            f"🔢 <b>VIN Kod:</b> {vin}\n"
            f"👤 <b>Mijoz:</b> {client_name}\n"
            f"📞 <b>Telefon:</b> {phone}\n"
            f"📋 <b>Topshirilgan:</b> {applied}\n"
            f"📅 <b>Tayyor bo'lish sanasi:</b> {issuance}",
            reply_markup=extra_services_kb()
        )
    else:
        await message.answer("❌ Xatolik yuz berdi. Ehtimol bu VIN allaqachon mavjud.", reply_markup=extra_services_kb())


# ---- Litsenziya Qidirish ----
@router.message(F.text == "🔎 Litsenziya tekshirish")
async def start_search_license(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(LicenseSearchState.vin)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Bekor qilish")
    await message.answer(
        "🔎 Litsenziyani tekshirish.\n\n🔢 Avtomobil VIN kodini kiriting:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(LicenseSearchState.vin)
async def lic_search_result(message: Message, state: FSMContext):
    if message.text == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("📋 Qo'shimcha xizmatlar:", reply_markup=extra_services_kb())
        return
    vin = (message.text or "").strip().upper()
    result = await get_license_by_vin(vin)
    await state.clear()
    if result:
        await message.answer(
            f"📜 <b>LITSENZIYA MA'LUMOTI</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔢 <b>VIN Kod:</b> <code>{result['vin']}</code>\n"
            f"👤 <b>Mijoz:</b> {result['name'] or '—'}\n"
            f"📞 <b>Telefon:</b> {result['phone'] or '—'}\n"
            f"📋 <b>Topshirilgan sana:</b> {result['applied']}\n"
            f"📅 <b>Tayyor bo'lish sanasi:</b> <b>{result['issuance']}</b>",
            reply_markup=extra_services_kb()
        )
    else:
        await message.answer(
            f"❌ <b>{vin}</b> VIN kodi bo'yicha litsenziya topilmadi.\nQayta urinib ko'ring.",
            reply_markup=extra_services_kb()
        )


# ====================================================
# MAIN POLLING START
# ====================================================
async def main():
    await init_db()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    
    print("🚀 Bot ishga tushmoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot o'chirildi.")
