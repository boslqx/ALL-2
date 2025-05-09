from flask import Blueprint, render_template, session, current_app
import sqlite3, os

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

@admin_bp.route('/admin')
def dashboard():
    user_id = session.get('user_id')
    admin_name = 'Admin'

    if user_id:
        try:
            db_path = os.path.join(current_app.instance_path, 'site.db')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM User WHERE UserID = ?", (user_id,))
            result = cursor.fetchone()
            
            if result:
                admin_name = f"Admin {result[0]}"
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    return render_template('admin.html', admin_name=admin_name, active_tab='dashboard')
