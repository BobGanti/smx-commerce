from __future__ import annotations

from pathlib import Path

from flask import Blueprint, redirect, render_template, request
from werkzeug.datastructures import FileStorage

from smx_commerce.core import CommerceRuntime


ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_FAVICON_EXTENSIONS = {".png", ".ico"}


def create_admin_home_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint(
        "smx_commerce_admin_home",
        __name__,
        template_folder="../templates",
    )

    @bp.route("/", methods=["GET"], strict_slashes=False)
    def admin_home():
        return render_template(
            "admin/home.html",
            commerce_config=runtime.config,
            message=request.args.get("message"),
            error=request.args.get("error"),
        )

    @bp.post("/branding/assets")
    def upload_branding_assets():
        try:
            assets_dir = Path(runtime.config.assets_dir).resolve()
            assets_dir.mkdir(parents=True, exist_ok=True)

            logo = request.files.get("logo")
            favicon = request.files.get("favicon")

            uploaded_any = False

            if _has_file(logo):
                _save_asset(
                    file=logo,
                    target=assets_dir / "logo.png",
                    allowed_extensions=ALLOWED_LOGO_EXTENSIONS,
                    label="logo",
                )
                uploaded_any = True

            if _has_file(favicon):
                _save_asset(
                    file=favicon,
                    target=assets_dir / "favicon.png",
                    allowed_extensions=ALLOWED_FAVICON_EXTENSIONS,
                    label="favicon",
                )
                uploaded_any = True

            if not uploaded_any:
                return redirect("/commerce/admin?error=No logo or favicon file was selected.", code=303)

            return redirect("/commerce/admin?message=Branding assets updated.", code=303)

        except ValueError as exc:
            return redirect(f"/commerce/admin?error={str(exc)}", code=303)

    return bp


def _has_file(file: FileStorage | None) -> bool:
    return file is not None and bool(file.filename)


def _save_asset(
    *,
    file: FileStorage,
    target: Path,
    allowed_extensions: set[str],
    label: str,
) -> None:
    original_name = file.filename or ""
    extension = Path(original_name).suffix.lower()

    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"Invalid {label} file type. Allowed: {allowed}")

    target.parent.mkdir(parents=True, exist_ok=True)

    # Always store canonical names. Existing logo/favicon are intentionally replaced
    # only when the admin uploads a new file.
    file.save(target)