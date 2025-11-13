from flask import request, g
import jwt  # PyJWT
PUBLIC_KEYS = {...}  # 팀원 쪽에서 제공 (또는 대칭키/비밀키)

def get_user_id_from_auth():
    """
    확실함: Authorization 헤더에서 JWT 검증 → sub(또는 preferred_username 등) 추출
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, PUBLIC_KEYS, algorithms=["RS256","HS256"], options={"verify_aud": False})
        return payload.get("sub") or payload.get("user_id")  # 팀 약속에 맞춰 선택
    except Exception:
        return None

def require_auth():
    uid = get_user_id_from_auth()
    if not uid:
        return None
    return uid
