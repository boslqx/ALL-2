from flask import Blueprint, render_template, session, current_app, request, jsonify
import sqlite3, os
from datetime import datetime

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


@manager_bp.route('/manager/activity-logs')
def get_activity_logs():
    try:
        db_path = os.path.join(current_app.instance_path, 'site.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get filter parameter if exists
        action_filter = request.args.get('action', 'all')

        query = """
            SELECT ActivityLog.*, User.Name as UserName 
            FROM ActivityLog 
            LEFT JOIN User ON ActivityLog.UserID = User.UserID
        """

        params = []

        if action_filter != 'all':
            query += " WHERE ActionType = ?"
            params.append(action_filter)

        query += " ORDER BY Timestamp DESC LIMIT 100"

        cursor.execute(query, params)
        logs = cursor.fetchall()

        # Convert to list of dictionaries
        logs_list = [dict(log) for log in logs]
        return jsonify(logs_list)



    except Exception as e:
        print(f"Error fetching logs: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()
