from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask.views import MethodView
from db.models import User
from db import db
import re
from datetime import datetime, timedelta
from flask_mail import Message
from extensions import mail
import secrets
import string
from werkzeug.security import generate_password_hash, check_password_hash  # Add this import

register_bp = Blueprint('register', __name__, template_folder='../templates')

class RegisterView(MethodView):
    def get(self, token=None):
        if token:
            user = User.query.filter(
                User.registration_token.isnot(None),
                User.registration_token == token,
                User.token_expiry > datetime.now()
            ).first()

            if not user:
                flash('Invalid or expired registration link', 'danger')
                return redirect(url_for('login.login'))

            session['register_email'] = user.Email
            session['register_token'] = token
            session['register_user_id'] = user.UserID  # Add this line
            return render_template('register_verify.html', token=token)

        return redirect(url_for('login.login'))

    def post(self, token=None):
        if token:
            # Handle verification step
            temp_password = request.form.get('temp_password')
            email = session.get('register_email')
            user_id = session.get('register_user_id')  # Get user_id from session

            if not email or not user_id:
                flash('Session expired. Please try the registration link again.', 'danger')
                return redirect(url_for('login.login'))

            user = User.query.get(user_id)  # Get user by ID instead of email

            if not user or not check_password_hash(user.Password, temp_password):  # Use check_password_hash
                flash('Invalid temporary password', 'danger')
                return render_template('register_verify.html', token=token)

            # Proceed to password setup
            return redirect(url_for('register.set_password'))

        return redirect(url_for('login.login'))

@register_bp.route('/set-password', methods=['GET', 'POST'])
def set_password():
    print("Set password route hit")  # Add this line
    if 'register_user_id' not in session:
        print("No user ID in session")  # Add this line
        return redirect(url_for('login.login'))

    if request.method == 'POST':
        print("POST request received")  # Add this line
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Password validation
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register_set_password.html')

        if len(new_password) < 8 or len(new_password) > 12:
            flash('Password must be 8 to 12 characters long', 'danger')
            return render_template('register_set_password.html')

        if not re.search(r'[0-9]', new_password):
            flash('Password must contain at least one number', 'danger')
            return render_template('register_set_password.html')

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            flash('Password must contain at least one special character', 'danger')
            return render_template('register_set_password.html')

        # Update user password and complete registration
        user = User.query.get(session['register_user_id'])
        if user:
            user.Password = generate_password_hash(new_password)  # Hash the new password
            user.registration_token = None
            user.token_expiry = None
            user.IsActive = True
            db.session.commit()

            # Clear session
            session.pop('register_email', None)
            session.pop('register_token', None)
            session.pop('register_user_id', None)

            flash('Registration complete! Please login with your new password.', 'success')
            return redirect(url_for('login.login'))

    return render_template('register_set_password.html')


def generate_registration(email):
    # Generate random 9-char temp password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(9))

    # Generate secure token
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(days=1)  # 24 hour expiry

    return temp_password, token, expiry


# Add URL rule with the correct endpoint name
register_bp.add_url_rule('/register/<token>', view_func=RegisterView.as_view('register_with_token'),
                         methods=['GET', 'POST'])