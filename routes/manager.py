from flask import Blueprint, render_template, session

manager_bp = Blueprint('manager', __name__, template_folder='../templates')

@manager_bp.route('/manager')
def dashboard():
    return render_template('manager.html', name=session.get('user_id'))
