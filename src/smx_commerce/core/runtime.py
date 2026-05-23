from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from smx_commerce.core.config import CommerceConfig
from smx_commerce.core.db import create_schema, make_engine, make_session_factory
from smx_commerce.core.schema import assert_schema_ready, get_missing_tables


@dataclass
class CommerceRuntime:
    config: CommerceConfig
    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def from_config(cls, config: CommerceConfig) -> "CommerceRuntime":
        engine = make_engine(
            database_url=config.database_url,
            echo_sql=config.echo_sql,
        )

        return cls(
            config=config,
            engine=engine,
            session_factory=make_session_factory(engine),
        )

    @classmethod
    def from_mapping(cls, values: dict | None) -> "CommerceRuntime":
        return cls.from_config(CommerceConfig.from_mapping(values))

    @classmethod
    def from_env(cls) -> "CommerceRuntime":
        return cls.from_config(CommerceConfig.from_env())

    def init_schema(self) -> None:
        create_schema(self.engine)

    def get_missing_tables(self) -> list[str]:
        return get_missing_tables(self.engine)

    def assert_schema_ready(self) -> None:
        assert_schema_ready(self.engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
