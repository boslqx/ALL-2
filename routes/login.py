from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask.views import MethodView
from werkzeug.security import check_password_hash
from db.models import User
from db import db

login_bp = Blueprint('login', __name__, template_folder='../templates')


class LoginView(MethodView):
    def get(self):
        return render_template('login.html')

    def post(self):
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(Username=username).first()

        if user and user.Password == password:
            session['user_id'] = user.UserID
            session['role'] = user.Role

            if user.Role == 'admin':
                return f"Welcome Admin {user.Name}"
            elif user.Role == 'manager':
                return f"Welcome Manager {user.Name}"
            elif user.Role == 'cashier':
                return f"Welcome Cashier {user.Name}"
            else:
                flash('Unknown role!', 'danger')
                return redirect(url_for('login.login'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login.login'))


# Register the view
login_bp.add_url_rule('/login', view_func=LoginView.as_view('login'), methods=['GET', 'POST'])
