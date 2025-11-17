from flask import Blueprint, jsonify
from ..utils.auth import resolve_user_id
from ..utils.api_alerts import (
    cancel_all_alerts,
    get_latest_alert,     # 👈 이거 추가
)

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")

@bp.post("/cancel")
def cancel_alert():
    user_id, _, _ = resolve_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401

    ok = cancel_all_alerts(user_id)
    if not ok:
        return jsonify({"ok": False, "error": "NO_ALERT"}), 404

    return jsonify({"ok": True})

@bp.get("/status")
def alert_status():
    """
    프론트에서 현재 신고 상태를 확인하는 용도
    """
    user_id, _, _ = resolve_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "UNAUTHORIZED"}), 401

    row = get_latest_alert(user_id)
    if not row:
        return jsonify({
            "ok": True,
            "alerting": False,
            "last_decision": None,
            "last_reason": None,
        })

    # ALERT / OK / CANCELLED 중 ALERT만 "신고 중"으로 취급
    alerting = (row["ai_decision"] == "ALERT")

    return jsonify({
        "ok": True,
        "alerting": alerting,
        "last_decision": row["ai_decision"],
        "last_reason": row["ai_reason"],
    })