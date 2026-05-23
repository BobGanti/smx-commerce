from __future__ import annotations

import argparse
import sys

from smx_commerce.core import CommerceConfig, CommerceRuntime, SchemaNotReadyError


def is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smx-commerce",
        description="smx-commerce package maintenance commands.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check-schema",
        help="Check whether the configured database has the required smx-commerce tables.",
    )
    check_parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Defaults to SMX_COMMERCE_DATABASE_URL or local SQLite.",
    )

    init_parser = subparsers.add_parser(
        "init-schema",
        help="Create smx-commerce tables. Intended for local/dev SQLite by default.",
    )
    init_parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Defaults to SMX_COMMERCE_DATABASE_URL or local SQLite.",
    )
    init_parser.add_argument(
        "--allow-non-sqlite-create-all",
        action="store_true",
        help="Explicitly allow create_all() against a non-SQLite database.",
    )

    return parser


def resolve_database_url(value: str | None) -> str:
    if value:
        return value

    return CommerceConfig.from_env().database_url


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    database_url = resolve_database_url(args.database_url)

    if args.command == "check-schema":
        runtime = CommerceRuntime.from_mapping({"database_url": database_url})
        missing_tables = runtime.get_missing_tables()

        if missing_tables:
            print("Schema is not ready.")
            print("Missing table(s): " + ", ".join(missing_tables))
            return 2

        print("Schema is ready.")
        return 0

    if args.command == "init-schema":
        if not is_sqlite_url(database_url) and not args.allow_non_sqlite_create_all:
            print(
                "Refusing to run create_all() against a non-SQLite database without "
                "--allow-non-sqlite-create-all.",
                file=sys.stderr,
            )
            print(
                "For production databases, prefer a reviewed migration process.",
                file=sys.stderr,
            )
            return 3

        runtime = CommerceRuntime.from_mapping({"database_url": database_url})
        runtime.init_schema()

        try:
            runtime.assert_schema_ready()
        except SchemaNotReadyError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        print("Schema initialized.")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
