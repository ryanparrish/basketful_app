#!/usr/bin/env bash
# Regenerate the Spanish translation catalog after adding/changing gettext
# strings, then fill in the new msgstr entries in
# locale/es/LC_MESSAGES/django.po and run compilemessages.
#
# Requires GNU gettext (macOS: brew install gettext).
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v brew >/dev/null 2>&1 && brew --prefix gettext >/dev/null 2>&1; then
    export PATH="$(brew --prefix gettext)/bin:$PATH"
fi

python manage.py makemessages -l es \
    --ignore=venv \
    --ignore=.venv \
    --ignore=node_modules \
    --ignore=frontend \
    --ignore=participant-frontend \
    --ignore=staticfiles \
    --ignore=food_orders \
    --ignore=coverage \
    --ignore=htmlcov
