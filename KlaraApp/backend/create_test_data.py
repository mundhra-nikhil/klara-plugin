"""
Quick script to create test data (client + document) for the current user.
Run this inside the docker container.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dao.client import Client
from src.models.dao.document import Document
from src.models.enum.document_type import DocumentType
from src.models.enum.document_status import DocumentStatus
from src.repositories.db_setup import AsyncSessionLocal, engine


async def create_test_data():
    """Create a test client and document."""
    user_id = uuid.UUID('19436c90-6de1-4145-a7df-9fa7d7dd9aea')  # Current user ID from logs

    async with AsyncSessionLocal() as session:
        try:
            # First create a test client
            test_client = Client(
                id=uuid.uuid4(),
                name="Test Client LLC",
                code="TEST_CLIENT",
                is_active=True,
                blob_container_name="test-client-docs",
                qa_rule_profile={"test": True},
                created_at=datetime.now(timezone.utc),
            )

            session.add(test_client)
            await session.flush()  # Get the client ID

            print(f"✅ Created test client: {test_client.id}")

            # Now create a test document assigned to this client and user
            test_doc = Document(
                id=uuid.uuid4(),
                client_id=test_client.id,  # Use the real client ID
                title="Test QC Document",
                document_type=DocumentType.FORMATTING,
                status=DocumentStatus.QC_REVIEW,
                blob_url="https://example.com/test.docx",
                blob_container="test-container",
                metadata={"test": True},
                assigned_specialist_id=user_id,
                storage_type="blob",
                editor_type="word",
                priority=3,  # SmallInteger, not string
                version=1,
                validation_mode="auto",
                submitted_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )

            session.add(test_doc)
            await session.commit()

            print(f"✅ Created test document: {test_doc.id}")
            print(f"   Title: {test_doc.title}")
            print(f"   Client: {test_client.name}")
            print(f"   Assigned to user: {user_id}")
            print(f"   Status: {test_doc.status}")
            print("\n🎉 Test data created successfully! You can now use the Workflows tab.")

        except Exception as e:
            print(f"❌ Error creating test data: {e}")
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(create_test_data())