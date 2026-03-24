import asyncio
from database.db import init_db
from bot import bot_app


async def main():
    await init_db()
    await bot_app.start()


if __name__ == "__main__":
    asyncio.run(main())
