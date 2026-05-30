from __future__ import annotations

from pathlib import Path
import secrets
from typing import Any

from werkzeug.utils import secure_filename

from smx_commerce.catalog.objects import ProductMedia, ProductMediaRole, validate_required_text


ALLOWED_PRODUCT_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}


CONTENT_TYPE_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def is_empty_upload(upload_file: Any | None) -> bool:
    return upload_file is None or not getattr(upload_file, "filename", "")


def store_product_image_upload(
    *,
    upload_file: Any | None,
    products_assets_dir: str | Path,
    product_public_id: str,
    media_role: ProductMediaRole | str,
    alt_text: str = "",
    sort_order: int = 0,
) -> ProductMedia | None:
    if is_empty_upload(upload_file):
        return None

    normalized_product_public_id = validate_required_text(
        product_public_id,
        "product_public_id",
    )

    role = media_role if isinstance(media_role, ProductMediaRole) else ProductMediaRole(media_role)

    original_filename = secure_filename(getattr(upload_file, "filename", "") or "")

    if not original_filename:
        return None

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_PRODUCT_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_PRODUCT_IMAGE_EXTENSIONS))
        raise ValueError(f"product image must be one of: {allowed}")

    base_products_dir = Path(products_assets_dir)
    product_dir = base_products_dir / normalized_product_public_id

    if role == ProductMediaRole.MAIN:
        relative_dir = Path(normalized_product_public_id)
        stored_filename = f"main{extension}"
        order = 0
    else:
        relative_dir = Path(normalized_product_public_id) / "gallery"
        token = secrets.token_hex(6)
        stem = Path(original_filename).stem or "image"
        safe_stem = secure_filename(stem)[:40] or "image"
        order = int(sort_order)
        stored_filename = f"{order:03d}-{token}-{safe_stem}{extension}"

    target_dir = base_products_dir / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / stored_filename
    upload_file.save(target_path)

    storage_path = (Path("products") / relative_dir / stored_filename).as_posix()
    url = f"/commerce/assets/{storage_path}"

    content_type = getattr(upload_file, "content_type", "") or CONTENT_TYPE_BY_EXTENSION.get(
        extension,
        "application/octet-stream",
    )

    return ProductMedia(
        url=url,
        media_role=role,
        storage_path=storage_path,
        filename=stored_filename,
        content_type=content_type,
        alt_text=alt_text or "",
        sort_order=order,
    )