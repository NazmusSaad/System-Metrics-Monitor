import ssl as _ssl
from urllib.parse import urlparse, parse_qs

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings


def _get_connect_args(url: str) -> dict:
    """Build connect_args with SSL if sslmode is present in the URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if qs.get("sslmode", [None])[0] in ("require", "verify-ca", "verify-full"):
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE  # Azure Flexible Server uses MS-managed certs
        return {"ssl": ctx}
    return {}


engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=_get_connect_args(settings.database_url),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
