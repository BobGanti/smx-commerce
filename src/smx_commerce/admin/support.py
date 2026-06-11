from __future__ import annotations

from flask import Blueprint, abort, jsonify, redirect, render_template, request

from smx_commerce.core import CommerceRuntime
from smx_commerce.support import SupportAnalysisService, SupportRepository
from smx_commerce.support.objects import SupportThreadPriority, SupportThreadStatus


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
        priority = request.args.get("priority") or None

        with runtime.session_scope() as session:
            repository = SupportRepository(session)
            threads = repository.list_threads(
                status=SupportThreadStatus(status) if status else None,
                priority=SupportThreadPriority(priority) if priority else None,
            )

        if admin_support_wants_html():
            return render_template(
                "admin/support_threads.html",
                threads=threads,
                status=status,
                priority=priority,
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

    @bp.post("/support/<thread_public_id>/analyze")
    def analyze_support_thread(thread_public_id: str):
        ai_client = getattr(runtime, "ai_client", None)

        if ai_client is None:
            if admin_support_wants_html():
                return redirect(f"/commerce/admin/support/{thread_public_id}?error=ai_client_required")

            return jsonify({"error": "ai_client is required to analyze support threads"}), 400

        with runtime.session_scope() as session:
            service = SupportAnalysisService(
                session=session,
                ai_client=ai_client,
            )
            result = service.triage_thread(thread_public_id)

        if admin_support_wants_html():
            return redirect(f"/commerce/admin/support/{thread_public_id}?message=triage_complete")

        return jsonify(
            {
                "issue_type": result.issue_type,
                "confidence": result.confidence,
                "summary": result.summary,
                "should_escalate": result.should_escalate,
                "missing_information": result.missing_information,
            }
        )

    @bp.post("/support/<thread_public_id>/compose-reply")
    def compose_support_reply(thread_public_id: str):
        ai_client = getattr(runtime, "ai_client", None)

        if ai_client is None:
            if admin_support_wants_html():
                return redirect(f"/commerce/admin/support/{thread_public_id}?error=ai_client_required")

            return jsonify({"error": "ai_client is required to compose support reply drafts"}), 400

        with runtime.session_scope() as session:
            service = SupportAnalysisService(
                session=session,
                ai_client=ai_client,
            )
            draft = service.compose_reply_draft(thread_public_id)

        if admin_support_wants_html():
            return redirect(f"/commerce/admin/support/{thread_public_id}?message=reply_draft_complete")

        return jsonify(
            {
                "body": draft.body,
                "tone": draft.tone,
                "needs_human_review": draft.needs_human_review,
                "next_actions": draft.next_actions,
            }
        )

    @bp.post("/support/<thread_public_id>/reply")
    def save_support_reply(thread_public_id: str):
        body = request.form.get("body", "")

        try:
            with runtime.session_scope() as session:
                repository = SupportRepository(session)
                message = repository.add_admin_message(
                    thread_public_id,
                    body=body,
                    sender_name="Support",
                    metadata={"source": "admin_reviewed_reply"},
                )
        except ValueError as exc:
            if admin_support_wants_html():
                return redirect(f"/commerce/admin/support/{thread_public_id}?error=reply_body_required")

            return jsonify({"error": str(exc)}), 400

        if admin_support_wants_html():
            return redirect(f"/commerce/admin/support/{thread_public_id}?message=reply_saved")

        return jsonify(
            {
                "public_id": message.public_id,
                "sender_type": message.sender_type.value,
                "body": message.body,
            }
        )

    @bp.post("/support/<thread_public_id>/status")
    def update_support_thread_status(thread_public_id: str):
        status = request.form.get("status", "")

        try:
            with runtime.session_scope() as session:
                repository = SupportRepository(session)
                thread = repository.update_thread_status(
                    thread_public_id,
                    status=status,
                )
        except ValueError as exc:
            if admin_support_wants_html():
                return redirect(f"/commerce/admin/support/{thread_public_id}?error=status_invalid")

            return jsonify({"error": str(exc)}), 400

        if admin_support_wants_html():
            return redirect(f"/commerce/admin/support/{thread_public_id}?message=status_updated")

        return jsonify(support_thread_to_dict(thread))

    @bp.post("/support/<thread_public_id>/priority")
    def update_support_thread_priority(thread_public_id: str):
        priority = request.form.get("priority", "")

        try:
            with runtime.session_scope() as session:
                repository = SupportRepository(session)
                thread = repository.update_thread_priority(
                    thread_public_id,
                    priority=priority,
                )
        except ValueError as exc:
            if admin_support_wants_html():
                return redirect(f"/commerce/admin/support/{thread_public_id}?error=priority_invalid")

            return jsonify({"error": str(exc)}), 400

        if admin_support_wants_html():
            return redirect(f"/commerce/admin/support/{thread_public_id}?message=priority_updated")

        return jsonify(support_thread_to_dict(thread))

    return bp
