from flask_mail import Mail
from functools import wraps
from flask import abort, session, redirect, url_for, flash, request

# Initialize Flask-Mail
mail = Mail()

# Generic role-based decorator
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page', 'error')
                return redirect(url_for('auth.login'))

            user_role = session.get('role')
            if user_role not in allowed_roles:
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Specific role decorators for convenience
def admin_required(f):
    return role_required('admin')(f)

def manager_required(f):
    return role_required('manager')(f)

def cashier_required(f):
    return role_required('cashier')(f)

# Apply to blueprint safely (with static exception)
def apply_role_protection(blueprint, role_name):
    @blueprint.before_request
    def before():
        if request.path.startswith('/static/'):
            return  # Allow static files through
        return role_required(role_name)(lambda: None)()
