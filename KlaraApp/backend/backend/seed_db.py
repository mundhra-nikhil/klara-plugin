import asyncio
import uuid
from src.repositories.db_setup import AsyncSessionLocal
from src.models.dao.department import Department
from src.models.dao.user import User
from src.models.dao.client import Client
from src.models.dao.checklist import QCChecklist
from src.models.dao.checklist_item import ChecklistItem
from src.models.enum.user_role import UserRole
from src.models.enum.document_type import DocumentType
from src.services.auth.auth_service import hash_password
from sqlalchemy import select

async def seed():
    async with AsyncSessionLocal() as db:
        # Create department
        dept_stmt = select(Department).where(Department.name == "GRSS QA")
        res = await db.execute(dept_stmt)
        dept = res.scalar_one_or_none()
        if not dept:
            dept = Department(
                id=uuid.uuid4(),
                name="GRSS QA",
                description="Global Document QA and Quality Control Team"
            )
            db.add(dept)
            await db.flush()

        # Seed users
        users_to_seed = [
            {
                "email": "kris.searcy@epiqglobal.com",
                "display_name": "Kris Searcy",
                "role": UserRole.INTAKE_COORDINATOR,
            },
            {
                "email": "rina.shah@epiqglobal.com",
                "display_name": "Rina Shah",
                "role": UserRole.DOC_SPECIALIST,
            },
            {
                "email": "mei.park@epiqglobal.com",
                "display_name": "Mei Park",
                "role": UserRole.QC_OPERATOR,
            },
            {
                "email": "alex.morgan@epiqglobal.com",
                "display_name": "Alex Morgan",
                "role": UserRole.PROOFREADER,
            }
        ]

        role_passwords = {
            UserRole.INTAKE_COORDINATOR: "Password123!",
            UserRole.DOC_SPECIALIST:     "Password123!",
            UserRole.QC_OPERATOR:        "Password123!",
            UserRole.PROOFREADER:        "Alex#7mR3p",
        }

        for u_data in users_to_seed:
            user_stmt = select(User).where(User.email == u_data["email"])
            res = await db.execute(user_stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=u_data["email"],
                    display_name=u_data["display_name"],
                    password_hash=hash_password(role_passwords[u_data["role"]]),
                    role=u_data["role"],
                    department_id=dept.id,
                    is_active=True
                )
                db.add(user)
                await db.flush()

        # Create Client
        client_stmt = select(Client).where(Client.name == "Whitford Lane")
        res = await db.execute(client_stmt)
        client = res.scalar_one_or_none()
        if not client:
            client = Client(
                id=uuid.uuid4(),
                name="Whitford Lane",
                code="WHIT",
                is_active=True,
                blob_container_name="whitford-lane",
                qa_rule_profile={}
            )
            db.add(client)
            await db.flush()

        from src.models.dao.validation_rule import ClientValidationRule
        from src.services.ai_jobs.poc_rules import rule_meta
        rule_stmt = select(ClientValidationRule).where(ClientValidationRule.client_id == client.id)
        res = await db.execute(rule_stmt)
        ruleset = res.scalar_one_or_none()
        if not ruleset:
            defaults = rule_meta()
            serialized_defaults = {str(k): v for k, v in defaults.items()}
            ruleset = ClientValidationRule(
                id=uuid.uuid4(),
                client_id=client.id,
                name="Default 18-Rule Set",
                rules=serialized_defaults,
                is_active=True
            )
            db.add(ruleset)
            await db.flush()


        # Create Checklist
        chk_stmt = select(QCChecklist).where(QCChecklist.name == "Whitford Lane — Litigation QC Checklist")
        res = await db.execute(chk_stmt)
        checklist = res.scalar_one_or_none()
        if not checklist:
            checklist = QCChecklist(
                id=uuid.uuid4(),
                document_type=DocumentType.FORMATTING,
                name="Whitford Lane — Litigation QC Checklist",
                version=1,
                schema_definition={},
                is_active=True
            )
            db.add(checklist)
            await db.flush()

        # Clear existing checklist items for this checklist (if any)
        clear_items_stmt = select(ChecklistItem).where(ChecklistItem.checklist_id == checklist.id)
        res = await db.execute(clear_items_stmt)
        existing_items = res.scalars().all()
        for item in existing_items:
            await db.delete(item)
        await db.flush()

        # Seed 15 checklist items corresponding to FIXTURES.QC_CHECKLIST
        checklist_items = [
            # Group: Document setup
            {"label": "Font family & size consistency", "desc": "Checks if the document uses standard approved fonts consistently.", "mapping": "formatting", "order": 1, "req": True},
            {"label": "Page size & margin verification", "desc": "Standard letter size with 1-inch margins.", "mapping": "formatting", "order": 2, "req": True},
            {"label": "Header & footer integration", "desc": "Consistent case name and document title in footers.", "mapping": "formatting", "order": 3, "req": True},
            
            # Group: Formatting
            {"label": "Line & paragraph spacing validity", "desc": "Check for correct line heights and double spacing where required.", "mapping": "style", "order": 4, "req": True},
            {"label": "Quotation mark orientation & styling", "desc": "Ensure all quotation marks are smart quotes and styled correctly.", "mapping": "style", "order": 5, "req": True},
            {"label": "Justification & alignment validation", "desc": "Confirm paragraphs are properly aligned.", "mapping": "style", "order": 6, "req": True},
            
            # Group: Numbering
            {"label": "Table of contents cross-link verification", "desc": "Verify all headings match TOC entries exactly.", "mapping": "consistency", "order": 7, "req": True},
            {"label": "Clause and section numbering integrity", "desc": "Ensure sequential section numbering with no skips.", "mapping": "consistency", "order": 8, "req": True},
            
            # Group: Citations
            {"label": "Table of authorities formatting", "desc": "Check Bluebook compliance for case citations.", "mapping": "compliance", "order": 9, "req": True},
            {"label": "Cross-reference validity checks", "desc": "Ensure references to schedules and exhibits are valid.", "mapping": "compliance", "order": 10, "req": True},
            
            # Group: Spelling
            {"label": "Standard spelling & grammar checks", "desc": "Check for spelling errors and grammatical slips.", "mapping": "spelling", "order": 11, "req": True},
            {"label": "Jurisdiction-specific style patterns", "desc": "Ensure correct regional spelling rules are applied.", "mapping": "spelling", "order": 12, "req": True},
            
            # Group: Manual review
            {"label": "Verify signatures & dates", "desc": "Confirm signature blocks are populated and dated correctly.", "mapping": None, "order": 13, "req": False},
            {"label": "Exhibits integrity check", "desc": "Check that all referenced exhibits are attached.", "mapping": None, "order": 14, "req": False},
            {"label": "Final readability & sense check", "desc": "Read through for flow and context.", "mapping": None, "order": 15, "req": False},
        ]

        for item in checklist_items:
            db_item = ChecklistItem(
                id=uuid.uuid4(),
                checklist_id=checklist.id,
                label=item["label"],
                description=item["desc"],
                ai_finding_type_mapping=item["mapping"],
                sort_order=item["order"],
                is_required=item["req"]
            )
            db.add(db_item)
        
        await db.commit()
        print("Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
