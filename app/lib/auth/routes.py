from flask import Blueprint, current_app, g, request, session, flash, render_template, redirect, url_for
from itsdangerous import URLSafeTimedSerializer
import re

from . import database as db
from ..email import send_email

auth = Blueprint('auth', __name__, template_folder="templates")

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.loads(token, salt=current_app.config['SECURITY_PASSWORD_SALT'], max_age=expiration)


def session_logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.permanent = True

@auth.route("/login", methods=['GET', 'POST'])
def login():

    if session.get('logged_in') is True:
            return redirect(url_for('store.root'))

    if request.method == 'GET':
        return render_template("auth/login.html")
    else:
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            return redirect(url_for('.login'))

        result = db.check_credentials(email, password)
        user = db.get_user(email=email)

        if result:

            if not user['confirmed']:
                flash("Account not confirmed.", 'danger')
                return render_template("auth/login.html")

            session['logged_in'] = True
            session['user_id'] = user['id']
            session.permanent = True
            return redirect(url_for('store.root'))

        else:
            session_logout()
            flash("Wrong e-mail/password!", 'danger')
            return render_template("auth/login.html")

@auth.route("/register", methods=['GET', 'POST'])
def register():
    if session.get('logged_in') is True:
        return redirect(url_for('store.root'))

    if request.method == 'GET':
        return render_template("auth/register.html", message=request.args.get('message'))
    else:
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        if not email or not password or not username:
            flash("Fill in the form!", 'danger')
            return render_template("auth/register.html")

        if not re.match(r"^[\w]{6,}$", username):
            flash("Wrong username. It should contain only letters and numbers and be 7-letters long or longer.", 'danger')
            return render_template("auth/register.html")

        if not re.match(r'^(?:[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$', email):
            flash("Wrong e-mail address.", 'danger')
            return render_template("auth/register.html")

        if db.user_exists(email=email):
            flash("Account already exists.", 'danger')
            return render_template("auth/register.html")
        if db.user_exists(username=username):
            return redirect(url_for('.register', message="Username already taken."))

        db.register(email, password, username)
        token = generate_confirmation_token(email)

        text_message = f"""Please confirm your email by clicking the link below:

    {url_for('.confirm_email', token=token, _external=True)}

    Thank you.
        """

        html_message = f"""Please confirm your email by clicking the link below:
    <br>
    <a href="{url_for('.confirm_email', token=token, _external=True)}">{url_for('.confirm_email', token=token, _external=True)}</a>
    <br>
    Thank you.
        """

        try:
            send_email("Confirm your account", text_message, html_message, email)
        except:
            flash("Error occured while sending confirmation email. Please contact admin, remember to provide your e-mail / username.", 'danger')
            return render_template("auth/register.html")

        flash("Account created! Please confirm your email.", 'success')
        return render_template("auth/confirm.html", message=f"Please confirm your account using link sent to your email: {email}.")

@auth.route("/confirm/<token>")
def confirm_email(token):
    email = confirm_token(token)
    user = db.get_user(email=email) if email else None

    if not email:
        flash("The confirmation link is invalid or has expired.", 'danger')
    elif not user:
        flash("Account got deleted or doesn't exist.", 'danger')
    elif user['confirmed']:
        flash("Account already confirmed. Please login.", 'info')
    else:
        db.confirm_user(email)
        flash("You have confirmed your account. Thanks!", 'success')

    return render_template("auth/confirm.html")

@auth.route("/change_password", methods=['POST'])
def change_password():

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')

    if not session.get('logged_in'):
        return redirect(url_for('store.root'))

    if not current_password or not new_password:
        flash("Fill in the form!", 'danger')
        return render_template("auth/profile.html")

    if not db.check_credentials(g.user['email'], current_password):
        flash("Wrong current password!", 'danger')
        return render_template("auth/profile.html")

    db.change_password(g.user['id'], new_password)
    flash("Password changed!", 'success')
    return render_template("auth/profile.html")

@auth.route("/profile")
def profile():
    if not g.user:
        session_logout()
        return redirect(url_for('.login'))

    return render_template("auth/profile.html")

@auth.route("/logout")
def logout():
    session_logout()
    return redirect(url_for('store.root'))
