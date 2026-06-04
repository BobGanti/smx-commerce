from __future__ import annotations
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request

from smx_commerce.catalog import CatalogService, ProductMediaRole
from smx_commerce.catalog.media_storage import store_product_image_upload
from smx_commerce.core import CommerceRuntime


def _delete_media_file_if_safe(*, assets_dir: str, storage_path: str) -> None:
    if not storage_path:
        return

    assets_root = Path(assets_dir).resolve()
    target_path = (assets_root / storage_path).resolve()

    try:
        target_path.relative_to(assets_root)
    except ValueError:
        raise ValueError("refusing to delete media file outside assets directory")

    if target_path.exists() and target_path.is_file():
        target_path.unlink()


def create_product_edit_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_product_edit_admin", __name__)

    @bp.get("/products/<slug>/edit")
    def edit_product(slug: str):
        with runtime.session_scope() as session:
            catalog = CatalogService(session)
            product = catalog.get_product(slug)
            categories = catalog.list_categories(include_archived=False)

        if product is None:
            return jsonify({"error": f"product not found: {slug}"}), 404

        return render_template(
            "admin/product_edit.html",
            product=product,
            categories=categories,
            commerce_config=runtime.config,
        )

    @bp.post("/products/<slug>/update")
    def update_product_from_form(slug: str):
        payload = request.form

        category_slugs = [
            item.strip()
            for value in request.form.getlist("category_slugs")
            for item in str(value).split(",")
            if item.strip()
        ]

        changes = {
            "name": payload.get("name", ""),
            "kind": payload.get("kind", "generic"),
            "summary": payload.get("summary", ""),
            "description": payload.get("description", ""),
            "status": payload.get("status", "draft"),
            "category_slugs": category_slugs,
            "sort_order": int(payload.get("sort_order", 0) or 0),
        }

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                updated = catalog.update_product(slug, **changes)

                main_image = store_product_image_upload(
                    upload_file=request.files.get("main_image"),
                    products_assets_dir=runtime.config.products_assets_dir,
                    product_public_id=updated.product_public_id,
                    media_role=ProductMediaRole.MAIN,
                    alt_text=updated.name,
                    sort_order=0,
                )

                if main_image is not None:
                    catalog.add_product_media(updated.product_public_id, main_image)

                gallery_uploads = request.files.getlist("gallery_images")
                next_gallery_sort_order = len(updated.gallery_images) + 1

                for index, gallery_upload in enumerate(gallery_uploads):
                    gallery_image = store_product_image_upload(
                        upload_file=gallery_upload,
                        products_assets_dir=runtime.config.products_assets_dir,
                        product_public_id=updated.product_public_id,
                        media_role=ProductMediaRole.GALLERY,
                        alt_text=updated.name,
                        sort_order=next_gallery_sort_order + index,
                    )

                    if gallery_image is not None:
                        catalog.add_product_media(updated.product_public_id, gallery_image)
                        
            return redirect(f"/commerce/admin/products/{updated.slug}", code=303)

        except (TypeError, ValueError) as exc:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                product = catalog.get_product(slug)
                categories = catalog.list_categories(include_archived=False)

            if product is None:
                return jsonify({"error": f"product not found: {slug}"}), 404

            return render_template(
                "admin/product_edit.html",
                product=product,
                categories=categories,
                error=str(exc),
                commerce_config=runtime.config,
            ), 400

    @bp.post("/products/<slug>/media/delete")
    def delete_product_media_from_form(slug: str):
        media_url = (request.form.get("media_url") or "").strip()

        if not media_url:
            return jsonify({"error": "media_url is required"}), 400

        try:
            with runtime.session_scope() as session:
                catalog = CatalogService(session)
                product = catalog.get_product(slug)

                if product is None:
                    return jsonify({"error": f"product not found: {slug}"}), 404

                media_item = next(
                    (item for item in product.media if item.url == media_url),
                    None,
                )

                if media_item is None:
                    return jsonify({"error": "media item not found"}), 404

                _delete_media_file_if_safe(
                    assets_dir=runtime.config.assets_dir,
                    storage_path=media_item.storage_path,
                )

                catalog.delete_product_media_by_url(
                    product.product_public_id,
                    media_url,
                )

            return redirect(f"/commerce/admin/products/{slug}/edit", code=303)

        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    return bp
