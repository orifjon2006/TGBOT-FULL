"""Telegram Bot — Entry Point.

Barcha routerlarni birlashtiradi va botni ishga tushiradi.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db

# Handler routerlarni import qilish
from handlers.common import router as common_router
from handlers.order import router as order_router
from handlers.search import router as search_router
from handlers.catalog import router as catalog_router
from handlers.admin import router as admin_router
from handlers.master import router as master_router
from handlers.groups import router as groups_router
from handlers.license import router as license_router


logging.basicConfig(level=logging.INFO, stream=sys.stdout)
log = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        log.error("BOT_TOKEN topilmadi! .env faylni tekshiring.")
        sys.exit(1)

    # Ma'lumotlar bazasini ishga tushirish
    await init_db()
    log.info("✅ Ma'lumotlar bazasi tayyor.")

    # Bot va Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Routerlarni ulash (tartib muhim!)
    # Spamdan himoya yopildi (foydalanuvchi iltimosiga ko'ra)
    # from middlewares import ThrottlingMiddleware
    # dp.message.middleware(ThrottlingMiddleware(limit=1.5))

    dp.include_routers(
        common_router,   # /start, cancel, refresh — birinchi
        order_router,    # Buyurtma yaratish
        license_router,  # Litsenziya
        search_router,   # Qidirish
        catalog_router,  # Kataloglar
        admin_router,    # Admin ishlar, statistika, tarix
        master_router,   # Usta paneli
        groups_router,   # Usta guruhlari
    )

    # Webhook'ni o'chirish va polling boshlash
    log.info("🚀 Bot ishga tushmoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.delete_my_commands()
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())