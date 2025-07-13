BLUESHEET - SALES/INVENTORY SYSTEM (Academic Submission)
========================================================

DESCRIPTION:
------------
A Flask-based sales and inventory management system with SQLite database(BlueSheet),
submitted for 4007CEM Computer Science Activity Led Learning.

KEY FEATURES:
-------------
✔ Product management (barcode support)
✔ Real-time stock alerts
✔ Sales recording with PDF invoices
✔ Demand forecasting 
✔ Role-based access:
	Manager: Supervise and oversee all operations, generate sales report, create employee account
	Admin: Manage stock, register products
	Cashier: Perform transactions, view transaction history

TEST ACCOUNTS:
--------------
• Manager: kangkang@gmail.com / Jackang3623
• Admin: bosliangqx@gmail.com /Bosco123!
• Cashier: buttersmooth@gmail.com / Jane8563

SETUP:
-------
1. Download project:
   git clone https://github.com/boslqx/ALL-2.git
   cd ALL-2

2. Set up Python environment:
   python -m venv venv
   venv\Scripts\activate  (Windows)

3. Run:
   pip install -r requirements.txt

4. Launch:
   run app.py 
	* Running on http://127.0.0.1:5000 ( for desktop )
	* Running on http://172.20.10.2:5000 ( for tablet/ ipad, recommended to be connected to personal hotspot)

DEPENDENCIES:
-------------
- Flask
- Flask-SQLAlchemy
- SQLite (included with Python)

FILES:
------
- Main code: app.py
- Database: instance/site.db
- Config: .env
