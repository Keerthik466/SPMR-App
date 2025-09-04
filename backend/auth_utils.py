from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from flask import jsonify

def role_required(allowed_roles):
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role", None)

            if role not in allowed_roles:
                return jsonify({"msg": "Permission denied"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper
