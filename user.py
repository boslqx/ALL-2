from app import app
from db import db
from db.models import User

with app.app_context():
    if not User.query.first():
        user1 = User(
            Username="010505",
            Password="Benlai3214",  
            Role="admin",
            Name="Benjamin Lai",
            Email="Laijinbenn@gmail.com"
        )

        user2 = User(
            Username="030723",
            Password="Jane8563",
            Role="cashier",
            Name="Jane Tan Butter",
            Email="buttersmooth@gmail.com"
        )

        user3 = User(
            Username="921021",
            Password="Jackang3623",
            Role="manager",
            Name="Jackson Kang",
            Email="kangkang@gmail.com"
        )

        db.session.add_all([user1, user2, user3])
        db.session.commit()
        print("✅ Users seeded successfully!")
    else:
        print("ℹ️ Users already exist. Skipping seeding.")