import asyncio
from sqlalchemy import select
from src.repositories.db_setup import AsyncSessionLocal
from src.models.dao.user import User
from src.models.dao.client import Client
from src.models.dao.department import Department
from src.models.dao.document import Document
from src.models.dao.checklist import QCChecklist
from src.models.dao.checklist_item import ChecklistItem
from src.models.dao.qc_finding import QCFinding
from src.models.dao.qc_review import QCReview

async def check_db():
    async with AsyncSessionLocal() as session:
        print("--- Users ---")
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}, PasswordHash: {u.password_hash is not None}")
        
        print("\n--- Clients ---")
        clients = (await session.execute(select(Client))).scalars().all()
        for c in clients:
            print(f"ID: {c.id}, Name: {c.name}, Code: {c.code}")
            
        print("\n--- Documents ---")
        docs = (await session.execute(select(Document))).scalars().all()
        for d in docs:
            print(f"ID: {d.id}, Title: {d.title}, Status: {d.status}")

        print("\n--- Checklists ---")
        checklists = (await session.execute(select(QCChecklist))).scalars().all()
        for c in checklists:
            print(f"ID: {c.id}, Name: {c.name}, Type: {c.document_type}")

if __name__ == '__main__':
    asyncio.run(check_db())
