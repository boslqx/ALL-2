from flask_mail import Mail
from functools import wraps
from flask import abort, session, redirect, url_for, flash

# Initialize Flask-Mail
mail = Mail()

# Role-based access control decorators
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page', 'error')
                return redirect(url_for('auth.login'))
                
            if session.get('role') != required_role:
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return role_required('admin')(f)

def manager_required(f):
    return role_required('manager')(f)

def cashier_required(f):
    return role_required('cashier')(f)
