from flask import Blueprint, render_template, session, current_app
import sqlite3, os

manager_bp = Blueprint('manager', __name__, template_folder='../templates')


@manager_bp.route('/manager')
def dashboard():
    user_id = session.get('user_id')
    manager_name = 'manager'

    if user_id:
        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
            result = cursor.fetchone()

            if result:
                manager_name = f"manager {result[0]}"

        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    return render_template('manager.html', manager_name=manager_name, active_tab='dashboard')
