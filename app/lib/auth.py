from flask import Blueprint, render_template, request, redirect, session, url_for, current_app
from itsdangerous import URLSafeTimedSerializer
import re

from . import email as email_system
from . import auth_database as auth_db

auth = Blueprint("auth", __name__, template_folder="templates")


@auth.before_request
def check_platform():
    user_id = session.get('id')
    if not user_id:
        session_logout()
        return
    else:
        user = auth_db.get_user(id=user_id)
        if user['banned']:
            session_logout()
            return render_template('auth/banned.html', reason=user['banned_reason'])


def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return None
    return email


def session_logout():
    session.pop('loggedIn', None)
    session.pop('id', None)
    session.permanent = True


def is_logged():
    if session.get('loggedIn'):
        return True
    else:
        return False


@auth.route("/login/")
def _login():
    if session.get("loggedIn") is True:
        return redirect("/home/")
    
    return render_template('auth/login.html.jinja', message=request.args.get('message'), color=request.args.get('color'))


@auth.route("/register")
def _register():
    if session.get("loggedIn") is True:
        return redirect("/home/")
    
    return render_template('auth/register.html', message=request.args.get('message'))


@auth.route("/check_login", methods=["GET", "POST"])
def _check_login():
    if request.method == "GET":
        return redirect("/login/")

    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return redirect("/login")
    
    result = auth_db.check_credentials(email, password)
    user = auth_db.get_user(email=email)

    if result:
        if not user['confirmed']:
            return redirect(url_for("._login", message="Account not confirmed."))
        
        if user['banned']:
            session_logout()
            return render_template('auth/banned.html', reason=user['banned_reason'])

        session['loggedIn'] = True
        session['id'] = auth_db.get_user_id(email=email)
        session.permanent = True
        return redirect(url_for("news._root"))
    
    else:
        session_logout()
        return redirect(url_for("._login", message="Wrong e-mail/password!", color="red"))


@auth.route('/confirm/<token>')
def _confirm_email(token):
    try:
        email = confirm_token(token)
    except Exception as e:
        return render_template("auth/confirm_email.html", message='The confirmation link is invalid or has expired.')
    if email is None:
        return render_template("auth/confirm_email.html", message='The confirmation link is invalid or has expired.')
    user = auth_db.get_user(email=email)
    if user is None:
        return render_template("auth/confirm_email.html", message='Account got deleted or doesn\'t exist.')
    if user['confirmed']:
        return render_template("auth/confirm_email.html", message='Account already confirmed. Please login.')
    else:
        auth_db.confirm_user(email)
        return render_template("auth/confirm_email.html", message='You have confirmed your account. Thanks! <br /><br /> <input type="button" class="Btn" onclick="window.location.href=\'/\'" value="Return to home page"></input>')


@auth.route("/check_register", methods=["GET", "POST"])
def _check_register():
    if request.method == "GET":
        return redirect("/register/")

    email = request.form.get("email")
    username = request.form.get("username")
    password = request.form.get("password")

    if not email or not password or not username:
        return redirect(url_for("._register", message="Fill in the form."))

    if not re.match(r"^[\w]{6,}$", username):
        return redirect(url_for("._register", message="Wrong username. It should contain only letters and numbers and be 7-letters long or longer."))
    
    if not re.match(r'^(?:[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$', email):
        return redirect(url_for("._register", message="Wrong e-mail address."))

    if auth_db.email_exists(email):
        return redirect(url_for("._register", message="Account already exists."))
    if auth_db.username_exists(username):
        return redirect(url_for("._register", message="Username already taken."))

    auth_db.register(email, password, username)
    token = generate_confirmation_token(email)

    text_message = f'''Please confirm your email by clicking the link below:

{url_for("._confirm_email", token=token, _external=True)}

Thank you.
    '''

    html_message = f'''Please confirm your email by clicking the link below:
<br>
<a href="{url_for("._confirm_email", token=token, _external=True)}">{url_for("._confirm_email", token=token, _external=True)}</a>
<br>
Thank you.
    '''

    try:
        email_system.send_email("Confirm your account", text_message, html_message, email)
    except:
        return redirect(url_for("._register", message="Error occured while sending confirmation email. Please contact admin, remember to provide your e-mail / username."))

    return render_template("auth/confirm_email.html", message=f"Please confirm your account using link sent to your email: {email}.")
    

@auth.route("/change_password", methods=["POST"])
def _change_password():

    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")

    if not is_logged():
        return redirect("/")

    if not current_password or not new_password:
        return redirect(url_for("._profile", message="Fill in the form!"))
    
    user_id = session['id']

    email = auth_db.get_user_email(id=user_id)
    if not auth_db.check_credentials(email, current_password):
        return redirect(url_for("._profile", message="Wrong current password!"))
    
    auth_db.change_password(user_id, new_password)

    return redirect(url_for("._profile", message="Password changed!"))

    
@auth.route("/profile")
def _profile():

    if not is_logged():
        session_logout()
        return redirect(url_for("._login"))
    
    return render_template("auth/profile.html", message=request.args.get('message'))


@auth.route("/logout")
def _logout():
    session_logout()
    return redirect("/")
