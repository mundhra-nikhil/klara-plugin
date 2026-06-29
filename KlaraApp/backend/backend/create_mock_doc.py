import asyncio
import uuid
from src.repositories.db_setup import AsyncSessionLocal
from src.models.dao.document import Document
from src.models.dao.client import Client
from src.models.enum.document_type import DocumentType
from sqlalchemy import select

MOCK_DOC_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

async def seed_doc():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Client).where(Client.name == "Whitford Lane"))
        client = res.scalar_one_or_none()
        if not client:
            print("Client not found")
            return
            
        doc = await db.get(Document, MOCK_DOC_ID)
        if not doc:
            doc = Document(
                id=MOCK_DOC_ID,
                client_id=client.id,
                title="Mock Document for Word Add-in",
                document_type=DocumentType.FORMATTING,
                blob_url="mock",
                blob_container="mock",
                metadata_={}
            )
            db.add(doc)
            await db.commit()
            print(f"Created mock document with ID {MOCK_DOC_ID}")
        else:
            print(f"Mock document already exists with ID {MOCK_DOC_ID}")

if __name__ == '__main__':
    asyncio.run(seed_doc())
