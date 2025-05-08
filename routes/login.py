from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask.views import MethodView
from db.models import User
from db import db
from flask import redirect, url_for

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
                return redirect(url_for('admin.admin_dashboard'))
            elif user.Role == 'manager':
                return redirect(url_for('manager.dashboard'))
            elif user.Role == 'cashier':
                return redirect(url_for('cashier.dashboard'))
            else:
                flash('Unknown role!', 'danger')
                return redirect(url_for('login.login'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login.login'))


login_bp.add_url_rule('/login', view_func=LoginView.as_view('login'), methods=['GET', 'POST'])

