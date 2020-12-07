import functools
from typing import Optional

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_babel import gettext
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.utils import escape

from psan.db import get_db
from psan.model import AccountRegisterForm, AccountType, LoginForm, PasswordResetForm
from psan.postman import password_reset

bp = Blueprint("auth", __name__, url_prefix="/auth")
_ = gettext


def login_required(view=None, role: Optional[AccountType] = None):
    """View decorator that redirects anonymous users to the login page."""

    # Make it work for @f and @f(role=XYZ), see https://stackoverflow.com/a/36739863
    if not view:
        return functools.partial(login_required, role=role)

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.account is None:
            flash(_("Log in needed"), category="info")
            return redirect(url_for("auth.login"))
        elif role and g.account["type"] != role.value:
            flash(_("Insufficient permission"), category="error")
            return redirect(url_for("account.index"))

        return view(**kwargs)

    return wrapped_view


@bp.before_app_request
def load_logged_in_account():
    """If a account id is stored in the session, load the account object from
    the database into ``g.account``."""
    account_id = session.get("account_id")

    g.account = None
    if account_id:
        g.account = (
            get_db().fetchone("SELECT * FROM account WHERE id = %s", (account_id,))
        )


def is_email_unique(db, email: str) -> bool:
    if db.fetchone("SELECT id FROM account WHERE email = %s", (email,)) is not None:
        flash(_("E-mail %(value)s is already taken.", value=escape(email)),
              category="error")
        return False
    else:
        return True


@bp.route("/register", methods=("GET", "POST"))
def register():
    """Register a new account.
    Validates that the email is not already taken. Handles password for security.
    """
    db = get_db()

    form = AccountRegisterForm(request.form)
    if request.method == "POST":

        if not form.validate():
            flash(_("Form content is not valid."), category="error")
        elif is_email_unique(db, form.email.data):
            db.execute(
                "INSERT INTO account (full_name, type, email, password) "
                "VALUES (%s, %s, %s, %s)",
                (form.full_name.data, form.type.data, form.email.data,
                 generate_password_hash("TODO")),
            )
            db.commit()
            session.clear()
            flash(_("Registration was successful."), category="message")
            return redirect(url_for("auth.login"))
        else:
            form.email.errors.append(_("Value is already taken."))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Log in a registered account by adding the account id to the session."""
    form = LoginForm(request.form)
    if request.method == "POST":
        error = False

        if not form.validate():
            flash(_("Form content is not valid."), category="error")
        else:
            db = get_db()
            account = db.fetchone(
                "SELECT * FROM account WHERE email = %s", (form.email.data,))

            if account is None:
                flash(_("Incorrect e-mail."), category="error")
                error = True
            elif not check_password_hash(account["password"], form.password.data):
                flash(_("Incorrect password."), category="error")
                error = True

            if error is False:
                # store the account id in a new session and return to the index
                session.clear()
                session["account_id"] = account["id"]
                return redirect(url_for("account.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout")
def logout():
    """Clear the current session, including the stored account id."""
    session.clear()
    return redirect(url_for("index"))


@bp.route("/reset", methods=("GET", "POST"))
def reset():
    """Send e-mail with link to reset password."""
    form = PasswordResetForm(request.form)
    if request.method == "POST":
        if not form.validate():
            flash(_("Form content is not valid."), category="error")
        else:
            db = get_db()
            account = db.fetchone(
                "SELECT * FROM account WHERE email = %s", (form.email.data,))

            if account is None:
                flash(_("Unknown e-mail."), category="error")
            else:
                password_reset(request.remote_addr, account["id"])
                flash(
                    _("Login and password reset link was sent to your e-mail address."), category="message")
                return redirect(url_for("index"))

    return render_template("auth/reset.html", form=form)