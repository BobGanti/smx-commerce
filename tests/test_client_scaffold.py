from pathlib import Path

from flask import Flask

from smx_commerce import ensure_commerce_scaffold, setup_commerce


def test_commerce_scaffold_creates_expected_client_files(tmp_path):
    scaffold = ensure_commerce_scaffold(project_root=tmp_path)

    assert scaffold.scaffold_dir == tmp_path / "commerce"
    assert scaffold.data_dir == tmp_path / "commerce" / "data"
    assert scaffold.db_file == tmp_path / "commerce" / "data" / "smx_commerce_dev.db"

    assert (tmp_path / "commerce").is_dir()
    assert (tmp_path / "commerce" / "data").is_dir()
    assert (tmp_path / "commerce" / "__init__.py").is_file()
    assert (tmp_path / "commerce" / "smx_commerce_setup.py").is_file()
    assert (tmp_path / "commerce" / ".smx_commerce_example.env").is_file()
    assert (tmp_path / "commerce" / ".smx_commerce.env").is_file()

    setup_text = (tmp_path / "commerce" / "smx_commerce_setup.py").read_text(
        encoding="utf-8"
    )
    example_text = (tmp_path / "commerce" / ".smx_commerce_example.env").read_text(
        encoding="utf-8"
    )
    env_text = (tmp_path / "commerce" / ".smx_commerce.env").read_text(
        encoding="utf-8"
    )

    assert "def setup_commerce" in setup_text
    assert "from smx_commerce import setup_commerce as _setup_commerce" in setup_text

    assert "SMX_COMMERCE_DATABASE_URL=sqlite+pysqlite:///./commerce/data/smx_commerce_dev.db" in example_text
    deprecated_admin_key_name = "SMX_COMMERCE_ADMIN_" + "API_KEY"
    assert deprecated_admin_key_name not in example_text
    assert "SMX_COMMERCE_SITE_TITLE=SyntaxMatrix" in example_text
    assert "SMX_COMMERCE_MODULE_TITLE=smxCommerce" in example_text

    assert "SMX_COMMERCE_DATABASE_URL=sqlite+pysqlite:///" in env_text
    assert "commerce/data/smx_commerce_dev.db" in env_text.replace("\\", "/")
    assert deprecated_admin_key_name not in env_text


def test_commerce_scaffold_does_not_overwrite_existing_customer_files(tmp_path):
    scaffold_dir = tmp_path / "commerce"
    scaffold_dir.mkdir()

    setup_file = scaffold_dir / "smx_commerce_setup.py"
    env_example_file = scaffold_dir / ".smx_commerce_example.env"
    env_file = scaffold_dir / ".smx_commerce.env"

    setup_file.write_text("# customer setup\n", encoding="utf-8")
    env_example_file.write_text("# customer example env\n", encoding="utf-8")
    env_file.write_text("# customer real env\n", encoding="utf-8")

    ensure_commerce_scaffold(project_root=tmp_path)

    assert setup_file.read_text(encoding="utf-8") == "# customer setup\n"
    assert env_example_file.read_text(encoding="utf-8") == "# customer example env\n"
    assert env_file.read_text(encoding="utf-8") == "# customer real env\n"


def test_setup_commerce_injects_scaffold_and_creates_dev_database(tmp_path):
    app = Flask(__name__)

    setup_commerce(
        app,
        project_root=tmp_path,
        init_schema=True,
    )

    assert (tmp_path / "commerce").is_dir()
    assert (tmp_path / "commerce" / "data").is_dir()
    assert (tmp_path / "commerce" / "smx_commerce_setup.py").is_file()
    assert (tmp_path / "commerce" / ".smx_commerce_example.env").is_file()
    assert (tmp_path / "commerce" / ".smx_commerce.env").is_file()
    assert (tmp_path / "commerce" / "data" / "smx_commerce_dev.db").is_file()

    client = app.test_client()

    response = client.get("/commerce/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"