from flask import Blueprint, render_template, session
import sqlite3

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

@admin_bp.route('/admin')
def dashboard():
    user_id = session.get('user_id')
    admin_name = 'Admin'

    if user_id:
        conn = sqlite3.connect('C:/Users/user/Documents/GitHub/ALL-2/instance/site.db')  # Correct this!
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            admin_name = f"Admin {result[0]}"

    return render_template('admin.html', admin_name=admin_name)
