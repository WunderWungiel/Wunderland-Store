import math

from flask import Blueprint, session, redirect, render_template, request, url_for

from . import database as db, config, auth_database as auth_db
from .auth import is_logged

submissions_bp = Blueprint("submissions", __name__, template_folder="templates")

@submissions_bp.before_request
def before_request():
    if not is_logged() or session['username'] not in config['ADMIN_USERNAMES']:
        return redirect("/")

@submissions_bp.route("/submission/<int:id>")
def _submission(id):

    submission = db.get_submissions(id)
    if not submission:
        return redirect("/submissions")
    
    return render_template("submissions/submission_page.html", app=submission)

@submissions_bp.route("/submission/<int:id>/delete")
def _delete_submission(id):

    submission = db.get_submissions(id)
    if not submission:
        return redirect("/submissions")
    
    db.delete_submission(id)
    return redirect("/submissions")

@submissions_bp.route("/submissions")
def _submissions_root():

    submissions = db.get_submissions()
    
    if not submissions:
        return render_template("submissions/submissions_empty.html")


    page_id = request.args.get('pageId', default=1, type=int)

    total_pages = math.ceil(len(submissions) / 10)

    if page_id < 1 or page_id > total_pages:
        return redirect(url_for("._submissions_root", pageId=1))

    next_page = page_id + 1 if page_id < total_pages else None
    previous_page = page_id - 1 if page_id > 1 else None

    first_index = (page_id - 1) * 10
    last_index = first_index + 10

    ids = list(submissions.keys())
    apps_to_show = ids[first_index:last_index]
    apps_to_show = [submissions[app_id] for app_id in apps_to_show]

    return render_template("submissions/submissions.html", apps=apps_to_show, next_page=next_page, previous_page=previous_page)