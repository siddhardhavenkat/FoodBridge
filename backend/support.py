"""Contact Us / Report-a-Problem module.

Lets a logged-in restaurant, NGO, or runner report an issue with an optional
photo/video attachment. Every report is visible to the admin dashboard along
with the reporter's full registration details.
"""
import os
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from db import mongo
from auth import login_required, ROLE_DASHBOARDS

support_bp = Blueprint("support", __name__, url_prefix="/support")

ALLOWED_ATTACHMENT_EXT = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "webm"}
CATEGORIES = ["App bug / error", "Map or GPS issue", "Payment / OTP problem",
              "Runner / delivery issue", "Account or profile issue", "Other"]


def _allowed_attachment(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_ATTACHMENT_EXT


@support_bp.route("/contact", methods=["GET", "POST"])
@login_required()
def contact():
    role = session.get("role")
    if role not in ("restaurant", "ngo", "runner"):
        flash("Contact support is available for restaurant, NGO, and runner accounts.", "error")
        return redirect(url_for(ROLE_DASHBOARDS.get(role, "auth.login")))

    if request.method == "POST":
        category = request.form.get("category", "Other")
        message = request.form.get("message", "").strip()
        if not message:
            flash("Please describe the problem before submitting.", "error")
            return redirect(url_for("support.contact"))

        attachment_path = ""
        file = request.files.get("attachment")
        if file and file.filename and _allowed_attachment(file.filename):
            filename = secure_filename(f"{session['user_id']}_{int(datetime.utcnow().timestamp())}_{file.filename}")
            upload_dir = os.path.join(current_app.root_path, "..", "static", "uploads", "issues")
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            attachment_path = f"uploads/issues/{filename}"

        user = mongo.db.users.find_one({"_id": ObjectId(session["user_id"])}) or {}
        issue = {
            "reporter_id": session["user_id"],
            "reporter_role": role,
            "reporter_name": session.get("name", user.get("name", "")),
            "reporter_phone": user.get("phone", ""),
            "reporter_email": user.get("email", ""),
            "category": category,
            "message": message,
            "attachment": attachment_path,
            "status": "Open",
            "created_at": datetime.utcnow(),
        }
        mongo.db.issues.insert_one(issue)
        current_app.logger.info("Issue reported by user_id=%s role=%s category=%s", session["user_id"], role, category)
        flash("Thanks — your issue has been sent to the FoodBridge team.", "success")
        return redirect(url_for(ROLE_DASHBOARDS.get(role)))

    my_issues = list(mongo.db.issues.find({"reporter_id": session["user_id"]}).sort("created_at", -1))
    return render_template("contact_us.html", categories=CATEGORIES, my_issues=my_issues)


@support_bp.route("/resolve/<issue_id>", methods=["POST"])
@login_required("admin")
def resolve_issue(issue_id):
    mongo.db.issues.update_one({"_id": ObjectId(issue_id)}, {"$set": {"status": "Resolved", "resolved_at": datetime.utcnow()}})
    flash("Issue marked as resolved.", "success")
    return redirect(url_for("admin.dashboard"))
