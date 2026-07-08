import os
from .settings import *          # import the default dev settings
DEBUG = False
ALLOWED_HOSTS = ['*']   # add IP or domain
# Secret key – keep it out of version control
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
# Optional: enable secure cookies
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
