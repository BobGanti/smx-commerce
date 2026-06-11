from smx_commerce.support.reply_safety import validate_admin_reply_body


def test_validate_admin_reply_body_allows_review_language():
    body = validate_admin_reply_body(
        "Hi Aoife, we are reviewing your refund request and will check the order before confirming the next step."
    )

    assert body.startswith("Hi Aoife")


def test_validate_admin_reply_body_rejects_completed_refund_claim():
    try:
        validate_admin_reply_body("Hi Aoife, your refund has been issued.")
    except ValueError as exc:
        assert "unsafe completed-action claim" in str(exc)
    else:
        raise AssertionError("Expected unsafe completed-action claim to be rejected")


def test_validate_admin_reply_body_rejects_completed_access_claim():
    try:
        validate_admin_reply_body("Hi Aoife, access has been restored.")
    except ValueError as exc:
        assert "unsafe completed-action claim" in str(exc)
    else:
        raise AssertionError("Expected unsafe completed-action claim to be rejected")
