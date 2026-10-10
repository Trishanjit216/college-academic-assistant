# College Academic Assistant
backend/ = Django API + admin panel, frontend/ = React app. Follow the step-by-step guide in chat.
Render Start Command:
python manage.py makemigrations core && python manage.py migrate && python manage.py collectstatic --noinput && python manage.py seed_demo && gunicorn config.wsgi:application
