from flask import Blueprint, render_template, session

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

@admin_bp.route('/admin')
def dashboard():
    return render_template('admin.html', name=session.get('user_id'))
