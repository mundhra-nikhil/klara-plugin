import asyncio
from sqlalchemy import select, update
from src.repositories.db_setup import AsyncSessionLocal
from src.models.dao.user import User
from src.services.auth.auth_service import hash_password

PROOFREADER_EMAIL = "alex.morgan@epiqglobal.com"
NEW_PASSWORD = "Alex#7mR3p"

async def reset():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == PROOFREADER_EMAIL))
        user = result.scalar_one_or_none()
        if not user:
            print(f"User {PROOFREADER_EMAIL} not found.")
            return
        user.password_hash = hash_password(NEW_PASSWORD)
        await db.commit()
        print(f"Password reset for {PROOFREADER_EMAIL}. New password: {NEW_PASSWORD}")

if __name__ == "__main__":
    asyncio.run(reset())
