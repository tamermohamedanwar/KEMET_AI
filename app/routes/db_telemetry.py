from flask import Blueprint, jsonify

from app.core.database_telemetry import database_telemetry


db_telemetry_bp = Blueprint("db_telemetry", __name__)


@db_telemetry_bp.route("/api/health/db", methods=["GET"])
def database_health():
    return jsonify(database_telemetry.snapshot())
