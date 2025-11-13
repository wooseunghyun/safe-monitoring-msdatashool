# scripts/server/utils/auth.py
import uuid
from flask import request, make_response, current_app
import jwt as pyjwt  # pip install PyJWT

COOKIE_KEY = "safe_uid"

def get_user_from_jwt():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): return None
    token = auth.split(" ", 1)[1]
    try:
        payload = pyjwt.decode(token, current_app.config["JWT_SECRET"],
                               algorithms=["HS256"], options={"verify_aud": False})
        return payload.get("sub") or payload.get("user_id")
    except Exception:
        return None

def resolve_user_id(resp=None):
    uid = get_user_from_jwt()
    if uid: return uid, resp, False

    dev = request.cookies.get(COOKIE_KEY)
    if dev: return dev, resp, False

    if not current_app.config["ALLOW_ANON_UPLOAD"]:
        return None, resp, False

    dev = f"device-{uuid.uuid4()}"
    if resp is None: resp = make_response()
    resp.set_cookie(COOKIE_KEY, dev, httponly=True, samesite="Lax", secure=True)
    return dev, resp, True
