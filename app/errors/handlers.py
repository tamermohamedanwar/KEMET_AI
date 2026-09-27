from flask import jsonify, render_template, request
from flask_wtf.csrf import CSRFError


def register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "csrf_failed", "message": str(error.description)}), 400
        return render_template("500.html"), 400

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "not_found"}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "internal_server_error"}), 500
        return render_template("500.html"), 500
