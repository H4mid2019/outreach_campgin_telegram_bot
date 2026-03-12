import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config import Config
from handlers import common, draft, autosend, oauth, campaigns
from database.db import init_db

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BotApp:
    def __init__(self):
        self.bot = Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        self.dp = Dispatcher(storage=MemoryStorage())
        
        # Include routers
        self.dp.include_router(campaigns.router)  # campaigns first — key auth states priority
        self.dp.include_router(common.router)
        self.dp.include_router(draft.router)
        self.dp.include_router(autosend.router)
        self.dp.include_router(oauth.router)

    async def start(self):
        """Start bot polling"""
        logger.info("Starting bot...")
        await init_db()
        await self.dp.start_polling(self.bot)

bot_app = BotApp()