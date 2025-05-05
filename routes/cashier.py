from flask import Blueprint, render_template, session

cashier_bp = Blueprint('cashier', __name__, template_folder='../templates')

@cashier_bp.route('/cashier')
def dashboard():
    return render_template('cashier.html', name=session.get('user_id'))
