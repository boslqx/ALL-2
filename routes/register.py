from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask.views import MethodView
from db.models import User
from db import db
import re
from datetime import datetime, timedelta
from flask_mail import Message
from extensions import mail
import secrets
import string
 
register_bp = Blueprint('register', __name__, template_folder='../templates')

class RegisterView(MethodView):
    def get(self, token=None):
        # Verify token if present
        if token:
            user = User.query.filter_by(registration_token=token).first()
            if not user or user.token_expiry < datetime.now():
                flash('Invalid or expired registration link', 'danger')
                return redirect(url_for('login.login'))
            
            session['register_email'] = user.Email
            session['temp_password'] = user.Password  # This should be the temp password
            return render_template('register_verify.html')
        
        return redirect(url_for('login.login'))

    def post(self):
        # Handle verification step
        if 'register_email' in session:
            email = session['register_email']
            temp_password = request.form.get('temp_password')
            user = User.query.filter_by(Email=email).first()
            
            if not user or user.Password != temp_password:
                flash('Invalid temporary password', 'danger')
                return redirect(request.url)
            
            # Proceed to password setup
            session['register_user_id'] = user.UserID
            return redirect(url_for('register.set_password'))
        
        return redirect(url_for('login.login'))

@register_bp.route('/set-password', methods=['GET', 'POST'])
def set_password():
    if 'register_user_id' not in session:
        return redirect(url_for('login.login'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Password validation (same as reset password)
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register.set_password'))

        if len(new_password) < 8 or len(new_password) > 12:
            flash('Password must be 8 to 12 characters long', 'danger')
            return redirect(url_for('register.set_password'))

        if not re.search(r'[0-9]', new_password):
            flash('Password must contain at least one number', 'danger')
            return redirect(url_for('register.set_password'))

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            flash('Password must contain at least one special character', 'danger')
            return redirect(url_for('register.set_password'))
        
        # Update user password and complete registration
        user = User.query.get(session['register_user_id'])
        if user:
            user.Password = new_password  # Hash this in production
            user.registration_token = None
            user.token_expiry = None
            user.IsActive = True
            db.session.commit()
            
            # Clear session
            session.pop('register_email', None)
            session.pop('temp_password', None)
            session.pop('register_user_id', None)
            
            flash('Registration complete! Please login with your new password.', 'success')
            return redirect(url_for('login.login'))
    
    return render_template('register_set_password.html')

# Helper function to generate temp password and token
def generate_registration(email):
    # Generate random 9-char temp password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(9))
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(days=1)  # 24 hour expiry
    
    return temp_password, token, expiry

register_bp.add_url_rule('/register/<token>', view_func=RegisterView.as_view('register'), methods=['GET', 'POST'])