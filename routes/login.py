from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask.views import MethodView
from db.models import User
from db import db
import random
import string
import re
from datetime import datetime, timedelta
from flask_mail import Message
from extensions import mail
from werkzeug.security import check_password_hash


login_bp = Blueprint('login', __name__, template_folder='../templates')


class LoginView(MethodView):
    def get(self):
        return render_template('login.html')
 
    def post(self):
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(Email=email).first()

        if user and check_password_hash(user.Password, password):  # 🔒 Secure check
            session['user_id'] = user.UserID
            session['role'] = user.Role

            if user.Role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.Role == 'manager':
                return redirect(url_for('manager.dashboard'))
            elif user.Role == 'cashier':
                return redirect(url_for('cashier.dashboard'))
            else:
                flash('Unknown role!', 'danger')
                return redirect(url_for('login.login'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login.login'))


@login_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login.login'))


login_bp.add_url_rule('/login', view_func=LoginView.as_view('login'), methods=['GET', 'POST'])

@login_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(Email=email).first()
        
        if user:
            # Generate 4-digit verification code
            verification_code = ''.join(random.choices(string.digits, k=4))
            session['reset_code'] = verification_code
            session['reset_email'] = email
            session['code_expiry'] = (datetime.now() + timedelta(minutes=15)).timestamp()
            
            # Send email (you need to configure Flask-Mail)
            msg = Message(
                "Password Reset Verification Code",
                recipients=[email],
                body=f"Your verification code is: {verification_code}\nThis code expires in 15 minutes."
            )
            mail.send(msg)
            
            flash('Verification code sent to your email', 'info')
            return redirect(url_for('login.verify_code'))
        else:
            flash('Email not found in our system', 'danger')
    
    return render_template('forgot_password.html')

@login_bp.route('/verify-code', methods=['GET', 'POST'])
def verify_code():
    if 'reset_email' not in session:
        return redirect(url_for('login.forgot_password'))
    
    if request.method == 'POST':
        user_code = request.form.get('verification_code')
        
        # Check if code is expired
        if datetime.now().timestamp() > session.get('code_expiry', 0):
            flash('Verification code has expired', 'danger')
            return redirect(url_for('login.forgot_password'))
        
        if user_code == session.get('reset_code'):
            return redirect(url_for('login.reset_password'))
        else:
            flash('Invalid verification code', 'danger')
    
    return render_template('verify_code.html')

@login_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        return redirect(url_for('login.forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Password format check
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('login.reset_password'))

        if len(new_password) < 8 or len(new_password) > 12:
            flash('Password must be 8 to 12 characters long', 'danger')
            return redirect(url_for('login.reset_password'))

        if not re.search(r'[0-9]', new_password):
            flash('Password must contain at least one number', 'danger')
            return redirect(url_for('login.reset_password'))

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            flash('Password must contain at least one special character', 'danger')
            return redirect(url_for('login.reset_password'))
        
        # Update user password
        user = User.query.filter_by(Email=session['reset_email']).first()
        if user:
            user.Password = new_password  # You should hash this password in production
            db.session.commit()
            
            # Clear the session
            session.pop('reset_code', None)
            session.pop('reset_email', None)
            session.pop('code_expiry', None)
            
            flash('Password updated successfully. Please login with your new password.', 'success')
            return redirect(url_for('login.login'))
    
    return render_template('reset_password.html')