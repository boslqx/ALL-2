from flask import Blueprint, render_template, session
import sqlite3

manager_bp = Blueprint('manager', __name__, template_folder='../templates')

@manager_bp.route('/manager')
def dashboard():
    user_id = session.get('user_id')


    conn = sqlite3.connect('C:/Users/user/Documents/GitHub/ALL-2/instance/site.db')
    cursor = conn.cursor()


    cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    name = result[0] if result else "Manager"

    return render_template('manager.html', name=name)
