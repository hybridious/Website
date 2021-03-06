from flask import (
    render_template, redirect, request, flash,
    url_for, abort, Blueprint, current_app as app,
    session,
)
from flask.ext.login import (
    login_user, login_required, logout_user, current_user,
)

from sqlalchemy import or_

from wtforms.validators import Required, Email, ValidationError
from wtforms import StringField, HiddenField, SubmitField

from main import db
from common import (
    set_user_currency, send_template_email, feature_flag,
)
from .common.forms import Form
from models.user import User, UserDiversity
from models.cfp import Proposal, CFPMessage
import re
from sqlalchemy.orm.exc import NoResultFound

users = Blueprint('users', __name__)


class NextURLField(HiddenField):
    def _value(self):
        # Cheap way of ensuring we don't get absolute URLs
        if not self.data or '//' in self.data:
            return ''
        if not re.match('^[-_0-9a-zA-Z/?=&]+$', self.data):
            app.logger.error('Dropping next URL %s', repr(self.data))
            return ''
        return self.data


class LoginForm(Form):
    email = StringField('Email', [Email(), Required()])
    next = NextURLField('Next')

    def validate_email(form, field):
        try:
            user = User.get_by_email(form.email.data)
        except NoResultFound:
            raise ValidationError('Email address not found')
        form._user = user

@users.route('/login/<email>')
@feature_flag('BYPASS_LOGIN')
def login_by_email(email):
    user = User.get_by_email(email)

    if current_user.is_authenticated():
        logout_user()

    login_user(user)
    session.permanent = True
    return redirect(request.args.get('next', url_for('tickets.main')))

@users.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated():
        return redirect(request.args.get('next', url_for('tickets.main')))

    if request.args.get('code'):
        user = User.get_by_code(app.config['SECRET_KEY'], request.args.get('code'))
        if user is not None:
            login_user(user)
            session.permanent = True
            return redirect(request.args.get('next', url_for('tickets.main')))
        else:
            flash("Your login link was invalid. Please note that they expire after 6 hours.")

    form = LoginForm(request.form, next=request.args.get('next'))
    if form.validate_on_submit():
        code = form._user.login_code(app.config['SECRET_KEY'])
        send_template_email('Electromagnetic Field: Login details',
                            to=form._user.email,
                            sender=app.config['TICKETS_EMAIL'],
                            template='emails/login-code.txt',
                            user=form._user, code=code, next_url=request.args.get('next'))
        flash("We've sent you an email with your login link")

    if request.args.get('email'):
        form.email.data = request.args.get('email')

    return render_template("login.html", form=form, next=request.args.get('next'))


@users.route("/logout")
@login_required
def logout():
    session.permanent = False
    logout_user()
    return redirect(url_for('base.main'))


@users.route("/set-currency", methods=['POST'])
def set_currency():
    if request.form['currency'] not in ('GBP', 'EUR'):
        abort(400)

    set_user_currency(request.form['currency'])
    return redirect(url_for('tickets.choose'))


class AccountForm(Form):
    name = StringField('Name', [Required()])
    age = StringField('Age')
    gender = StringField('Gender')
    ethnicity = StringField('Ethnicity')

    forward = SubmitField('Update')

@users.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = AccountForm()

    if form.validate_on_submit():
        if not current_user.diversity:
            current_user.diversity = UserDiversity()
            current_user.diversity.user_id = current_user.id
            db.session.add(current_user.diversity)

        current_user.name = form.name.data
        current_user.diversity.age = form.age.data
        current_user.diversity.gender = form.gender.data
        current_user.diversity.ethnicity = form.ethnicity.data

        app.logger.info('%s updated user information', current_user.name)
        db.session.commit()

        flash("Your details have been saved.")
        return redirect(url_for('.account'))

    if request.method != 'POST':
        # This is a required field so should always be set
        form.name.data = current_user.name

        if current_user.diversity:
            form.age.data = current_user.diversity.age
            form.gender.data = current_user.diversity.gender
            form.ethnicity.data = current_user.diversity.ethnicity

    unread_count = CFPMessage.query\
        .join(Proposal)\
        .filter(Proposal.user_id == current_user.id,
                Proposal.id == CFPMessage.proposal_id,
                CFPMessage.is_to_admin.is_(False),
                or_(CFPMessage.has_been_read.is_(False),
                    CFPMessage.has_been_read.is_(None)))\
        .count()

    return render_template("account.html", form=form, unread_count=unread_count)
