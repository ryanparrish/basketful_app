
# 🧭 Project Structure — Lyn Project

This document outlines the folder and file hierarchy for the **Lyn Project**,  
a Django-based application with modular apps (`core`, `food_orders`, etc.).

Use this as a quick reference for navigating the codebase and understanding where key logic lives —  
such as models, views, utils, and orchestration helpers.

---

## 📂 Folder Tree


lyn_project/
├── __pycache__/
├── coaches/
├── core/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── middleware.py
│   ├── migrations/
│   ├── models.py
│   ├── tests.py
│   └── views.py
├── food_orders/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── admin/
│   ├── admin.py
│   ├── apps.py
│   ├── balance_utils.py
│   ├── forms.py
│   ├── inlines.py
│   ├── logging.py
│   ├── middleware.py
│   ├── migrations/
│   ├── models.py
│   ├── queryset.py
│   ├── signals.py
│   ├── static/
│   ├── tasks.py
│   ├── templates/
│   ├── tests/
│   ├── user_utils.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── __pycache__/
│   │   ├── order_helper.py
│   │   ├── order_utils.py
│   │   └── order_validation.py
│   ├── utils.py
│   ├── validators.py
│   ├── views.py
│   ├── voucher_utils.py
│   └── widgets.py
├── lyn_app/
├── media/
├── staticfiles/
├── db.sqlite3
├── docker-compose.yml
├── Dockerfile
├── LICENSE
├── manage.py
├── models.dot
├── pytest.ini
├── README.md
└── requirements.txt
