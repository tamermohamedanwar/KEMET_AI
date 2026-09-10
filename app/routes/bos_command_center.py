from flask import Blueprint, render_template
from flask_login import login_required


bos_command_center_bp = Blueprint(
    "bos_command_center",
    __name__,
)


@bos_command_center_bp.get("/admin/automation/command-center")
@login_required
def command_center():
    return render_template("admin/command_center.html")
