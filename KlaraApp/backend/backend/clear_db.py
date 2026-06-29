"""Clear transactional row data from the database while preserving seed/lookup tables.

Truncates every table in the `public` schema EXCEPT those in PRESERVE.
Uses RESTART IDENTITY CASCADE so sequences reset and FK references are handled.
Table/column/index definitions and migration markers are always kept.

Protected tables (never truncated):
  - alembic_version     schema/migration state
  - departments         seed department(s)
  - users               seed user accounts
  - clients             seed client records
  - qc_checklists       seed QC checklist definitions
  - checklist_items     seed checklist line items

Run inside the backend container:
    docker exec -it klara-backend python clear_db.py
    docker exec -it klara-backend python clear_db.py --yes   # skip confirmation

Re-seed afterwards with:  docker exec klara-backend python seed_db.py
"""
import asyncio
import sys

from sqlalchemy import text

from src.repositories.db_setup import engine

# Tables whose rows must NEVER be deleted.
# Includes both migration state and all seed/lookup data populated by seed_db.py.
PRESERVE = {
    "alembic_version",    # Alembic migration marker — always keep
    "departments",        # Seed department(s)
    "users",              # Seed user accounts
    "clients",            # Seed client records
    "qc_checklists",      # Seed QC checklist definitions
    "checklist_items",    # Seed checklist line items
}


async def clear() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        )
        all_tables = [row[0] for row in result]
        tables = [t for t in all_tables if t not in PRESERVE]

        if not tables:
            print("No data tables found in 'public' schema — nothing to clear.")
            return

        quoted = ", ".join(f'"{t}"' for t in sorted(tables))
        await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        print(f"Cleared {len(tables)} table(s): {', '.join(sorted(tables))}")

        preserved_present = [t for t in all_tables if t in PRESERVE]
        if preserved_present:
            print(f"Preserved (seed/lookup data): {', '.join(sorted(preserved_present))}")

    await engine.dispose()


def main() -> None:
    if "--yes" not in sys.argv and "-y" not in sys.argv:
        reply = input(
            "This will DELETE ALL ROWS from every transactional table "
            "(seed/lookup tables are kept). Type 'yes' to continue: "
        ).strip().lower()
        if reply != "yes":
            print("Aborted — no changes made.")
            return
    asyncio.run(clear())
    print("Done.")


if __name__ == "__main__":
    main()
