"""Local dev helper: check Postgres connectivity and migration state (prints no secrets)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import asyncpg  # noqa: E402

from app.core.config import settings  # noqa: E402


async def main() -> int:
    url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
    try:
        conn = await asyncpg.connect(url, timeout=5)
    except Exception as exc:  # report the error class only, never the URL/password
        print(f"DB_FAIL {type(exc).__name__}: {str(exc)[:150]}")
        return 1
    version = (await conn.fetchval("select version()")).split(",")[0]
    tables = await conn.fetch(
        "select table_name from information_schema.tables where table_schema='public'"
    )
    try:
        rev = await conn.fetchval("select version_num from alembic_version")
    except asyncpg.UndefinedTableError:
        rev = None
    print(f"DB_OK {version} tables={len(tables)} alembic={rev}")
    await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
