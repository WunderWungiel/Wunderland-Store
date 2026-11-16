from datetime import datetime, timezone
import re

from flask import Blueprint, current_app, g, request, session, flash, render_template, redirect, url_for
from psycopg.errors import UniqueViolation

from .. import csrf
from .. import db
from .. import email
from .. import utils

auth = Blueprint('auth', __name__, template_folder="templates")


@auth.route("/login", methods=['GET', 'POST'])
def login():

    if g.user:
        return redirect(url_for('store.root'))

    if request.method == 'GET':
        return render_template("auth/login.html")

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password')

    if not email or not password:
        flash("Missing parameters!", "danger")
        return redirect(url_for('.login'))

    user = db.check_credentials(email, password)

    if not user:
        flash("Invalid credentials!", "danger")
        return redirect(url_for('.login'))

    if not user['confirmed']:
        flash("Please confirm your email!", "danger")
        return redirect(url_for('.login'))

    session['token'] = db.create_session(user['id'])

    flash("Logged in!", "success")
    return redirect(url_for('store.root'))


@auth.route("/register", methods=['GET', 'POST'])
def register():

    if g.user:
        return redirect(url_for('store.root'))

    if request.method == 'GET':
        return render_template("auth/register.html")

    user_email = request.form.get('email', '').strip().lower()
    username = request.form.get('username')
    password = request.form.get('password')

    def fail(message):
        flash(message, "danger")
        return redirect(url_for('.register'))

    if not all([user_email, username, password]):
        return fail("Fill in the form!")

    if not re.fullmatch(r"[A-Za-z0-9]{7,}", username):
        return fail("Wrong username. It should contain only letters and numbers and be 7-letters long or longer.")

    if not re.match(r'^(?:[a-z0-9!#$%&\'*+/=?^_{|}-]+(?:\.[a-z0-9!#$%&\'*+/=?^_{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$', user_email):
        return fail("Wrong e-mail address.")

    if db.get_user_by_email(user_email):
        return fail("Account already exists.")

    if db.get_user_by_username(username):
        return fail("Username already taken.")

    try:
        user = db.register(user_email, password, username)
    except UniqueViolation as e:
        if e.diag.constraint_name == 'users_username_key':
            return fail("Username already taken.")
        return fail("Account already exists.")

    confirm_url = utils.external_url_for('auth.confirm', token=user['confirmation_token'])

    try:
        email.send_email(
            "Confirm your account",
            f"Please confirm your email by clicking the link below:\n{confirm_url}\nThank you.",
            f"Please confirm your email by clicking the link below:<br><a href=\"{confirm_url}\">{confirm_url}</a><br>Thank you.",
            user_email
        )
    except Exception:
        current_app.logger.exception("Failed to send the confirmation email")
        db.delete_user(user['id'])
        return fail("Could not send the confirmation email. Please try again later.")

    flash("Account created! Please confirm your email.", "success")
    return render_template("auth/confirm.html")


@auth.route("/confirm/<token>")
def confirm(token):

    user = db.check_confirmation_token(token)

    if not user or user['confirmation_token_expires_at'] < datetime.now(timezone.utc):
        flash("The confirmation link is invalid or has expired.", "danger")
    else:
        db.confirm_user(user['id'])
        flash("You have confirmed your account. Thanks!", "success")

    return render_template("auth/confirm.html")


@auth.route("/change_password", methods=['POST'])
def change_password():

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')

    if not g.user:
        return redirect(url_for('store.root'))

    if not current_password or not new_password:
        flash("Fill in the form!", "danger")
        return render_template("auth/profile.html")

    if not db.check_credentials(g.user['email'], current_password):
        flash("Wrong current password!", "danger")
        return render_template("auth/profile.html")

    db.change_password(g.user['id'], new_password)
    flash("Password changed!", "success")

    return render_template("auth/profile.html")


@auth.route("/profile")
def profile():
    if not g.user:
        return redirect(url_for('.login'))

    return render_template("auth/profile.html")


@auth.route("/logout")
def logout():
    if not g.user:
        return redirect(url_for('.login'))

    if not csrf.is_valid(request.args.get(csrf.FIELD_NAME)):
        return redirect(url_for('.profile'))

    db.delete_session(session.get('token'))
    session.pop('token', None)

    flash("Logged out!", "success")
    return redirect(url_for('store.root'))
