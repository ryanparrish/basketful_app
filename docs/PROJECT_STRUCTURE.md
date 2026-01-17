# 🧭 Project Structure — Lyn Project

This document outlines the folder and file hierarchy for the **Lyn Project**,  
a Django-based application with modular apps (`core`, `lifeskills`, `pantry`, etc.).

Use this as a quick reference for navigating the codebase and understanding where key logic lives —  
such as models, views, utils, and orchestration helpers.

---

## 📂 Folder Tree

lyn_project/
├── .DS_Store
├── .dockerignore
├── .env
├── .git/
├── .github/
├── .gitignore
├── .pytest_cache/
├── .venv/
├── .vscode/
├── Dockerfile
├── LICENSE
├── PROJECT_STRUCTURE.md
├── README.md
├── __pycache__/
├── account/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── migrations/
│   ├── models.py
│   ├── signals.py
│   ├── tests.py
│   ├── utils/
│   └── views.py
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
├── lifeskills/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── admin.py
│   ├── apps.py
│   ├── migrations/
│   ├── models.py
│   ├── queryset.py
│   ├── signals.py
│   ├── tests.py
│   └── views.py
├── log/
├── core/
├── manage.py
├── media/
├── models.dot
├── old_requirements.txt
├── orders/
├── pantry/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── admin/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── inlines.py
│   ├── management/
│   ├── middleware.py
│   ├── migrations/
│   ├── models.py
│   ├── signals.py
│   ├── static/
│   ├── tasks/
│   ├── templates/
│   ├── tests/
│   ├── utils/
│   ├── validators.py
│   ├── views.py
│   └── widgets.py
├── pytest.ini
├── rename_migrations_app.py
├── requirements.txt
├── staticfiles/
└── voucher/
