import os
from datetime import timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)
from marshmallow import ValidationError

from models import AuthRequestSchema


auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def init_jwt(app):
    app.config["JWT_SECRET_KEY"] = app.config.get("JWT_SECRET_KEY") or os.environ.get("JWT_SECRET_KEY", "change-me")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = app.config.get("JWT_ACCESS_TOKEN_EXPIRES", timedelta(minutes=30))
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = app.config.get("JWT_REFRESH_TOKEN_EXPIRES", timedelta(days=7))
    jwt = JWTManager(app)
    return jwt


@auth_bp.route("/token", methods=["POST"])
def issue_token():
    schema = AuthRequestSchema()
    try:
        payload = schema.load(request.get_json(force=True))
    except ValidationError as err:
        return jsonify({"status": "error", "message": err.messages}), 400

    api_key = (payload.get("api_key") or "").strip()
    configured = (os.environ.get("API_SECRET_KEY", "") or "").strip() or (current_app.config.get("API_KEY") if current_app else "")
    if not configured:
        return jsonify({"status": "error", "message": "Server API key not configured"}), 500
    if api_key != configured:
        return jsonify({"status": "error", "message": "Invalid API key"}), 401

    identity = {"api_key_id": "primary"}
    access = create_access_token(identity=identity)
    refresh = create_refresh_token(identity=identity)
    return jsonify({
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer"
    }), 200


