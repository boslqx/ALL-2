import sqlite3
from werkzeug.security import generate_password_hash

db_path = 'instance/site.db'  
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT UserID, Password FROM User")
users = cursor.fetchall()

updated = 0
for user_id, password in users:
    if not password.startswith('pbkdf2:') and not password.startswith('scrypt:'):
        hashed = generate_password_hash(password)
        cursor.execute("UPDATE User SET Password = ? WHERE UserID = ?", (hashed, user_id))
        updated += 1
        print(f"Updated password for UserID {user_id}")

conn.commit()
conn.close()

print(f"✅ Done. {updated} password(s) upgraded to hashed format.")
