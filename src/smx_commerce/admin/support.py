from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request

from smx_commerce.core import CommerceRuntime
from smx_commerce.support import SupportRepository
from smx_commerce.support.objects import SupportThreadStatus


def admin_support_wants_html() -> bool:
    requested_format = request.args.get("format", "").lower()

    if requested_format == "html":
        return True

    if requested_format == "json":
        return False

    return request.accept_mimetypes.best_match(["text/html", "application/json"]) == "text/html"


def support_thread_to_dict(thread) -> dict:
    return {
        "public_id": thread.public_id,
        "customer_email": thread.customer_email,
        "customer_name": thread.customer_name,
        "subject": thread.subject,
        "order_public_id": thread.order_public_id,
        "status": thread.status.value,
        "priority": thread.priority.value,
        "issue_type": thread.issue_type,
        "source": thread.source,
        "metadata": thread.metadata,
        "created_at": thread.created_at.isoformat() if thread.created_at else None,
        "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
    }


def create_support_admin_blueprint(runtime: CommerceRuntime) -> Blueprint:
    bp = Blueprint("smx_commerce_support_admin", __name__)

    @bp.get("/support")
    def list_support_threads():
        status = request.args.get("status") or None

        with runtime.session_scope() as session:
            repository = SupportRepository(session)
            threads = repository.list_threads(
                status=SupportThreadStatus(status) if status else None,
            )

        if admin_support_wants_html():
            return render_template(
                "admin/support_threads.html",
                threads=threads,
                status=status,
                commerce_config=runtime.config,
            )

        return jsonify([support_thread_to_dict(thread) for thread in threads])

    @bp.get("/support/<thread_public_id>")
    def view_support_thread(thread_public_id: str):
        with runtime.session_scope() as session:
            repository = SupportRepository(session)
            detail = repository.get_thread_with_messages(thread_public_id)

        if detail is None:
            abort(404)

        if admin_support_wants_html():
            return render_template(
                "admin/support_thread_detail.html",
                detail=detail,
                commerce_config=runtime.config,
            )

        return jsonify(
            {
                "thread": support_thread_to_dict(detail.thread),
                "messages": [
                    {
                        "public_id": message.public_id,
                        "sender_type": message.sender_type.value,
                        "sender_email": message.sender_email,
                        "body": message.body,
                        "metadata": message.metadata,
                        "created_at": message.created_at.isoformat() if message.created_at else None,
                    }
                    for message in detail.messages
                ],
            }
        )

    return bp
