from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str, echo_sql: bool = False) -> Engine:
    connect_args = {}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        echo=echo_sql,
        future=True,
        connect_args=connect_args,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


def create_schema(engine: Engine) -> None:
    # Import models so SQLAlchemy registers their tables before create_all().
    import smx_commerce.catalog.models  # noqa: F401
    import smx_commerce.checkout.models  # noqa: F401
    import smx_commerce.customers.models  # noqa: F401
    import smx_commerce.payments.models  # noqa: F401
    import smx_commerce.core.settings_models  # noqa: F401
    import smx_commerce.support.models  # noqa: F401

    Base.metadata.create_all(engine)
