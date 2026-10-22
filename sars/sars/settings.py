import os
from pathlib import Path
from urllib.parse import urlparse, unquote

BASE_DIR = Path(__file__).resolve().parent.parent

# --- tiny .env loader (local development) ---
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def env(name, default=''):
    return os.environ.get(name, default)


SECRET_KEY = env('SECRET_KEY', 'dev-only-insecure-key-change-me')
DEBUG = env('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.onrender.com']
CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']
_extra_host = env('RENDER_EXTERNAL_HOSTNAME') or env('SITE_HOST')
if _extra_host:
    ALLOWED_HOSTS.append(_extra_host)
    CSRF_TRUSTED_ORIGINS.append('https://' + _extra_host)
if env('ALLOWED_HOSTS'):
    ALLOWED_HOSTS += [h.strip() for h in env('ALLOWED_HOSTS').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sars.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context.globals',
    ]},
}]

WSGI_APPLICATION = 'sars.wsgi.application'
AUTH_USER_MODEL = 'core.User'


# ---------------- Database: MySQL (PyMySQL driver) or SQLite fallback ----------------
def _mysql_config():
    url = env('DATABASE_URL') or env('MYSQL_ADDON_URI')
    if url:
        u = urlparse(url)
        return dict(NAME=u.path.lstrip('/'), USER=unquote(u.username or ''), PASSWORD=unquote(u.password or ''),
                    HOST=u.hostname or '', PORT=str(u.port or 3306))
    if env('DB_NAME') or env('MYSQL_ADDON_DB'):
        return dict(NAME=env('DB_NAME') or env('MYSQL_ADDON_DB'),
                    USER=env('DB_USER') or env('MYSQL_ADDON_USER'),
                    PASSWORD=env('DB_PASSWORD') or env('MYSQL_ADDON_PASSWORD'),
                    HOST=env('DB_HOST') or env('MYSQL_ADDON_HOST', '127.0.0.1'),
                    PORT=env('DB_PORT') or env('MYSQL_ADDON_PORT', '3306'))
    return None


_mysql = _mysql_config()
if _mysql:
    import pymysql
    pymysql.version_info = (2, 2, 1, 'final', 0)   # satisfy Django's mysqlclient version check
    pymysql.install_as_MySQLdb()
    DATABASES = {'default': dict(ENGINE='django.db.backends.mysql',
                                 OPTIONS={'charset': 'utf8mb4'}, CONN_MAX_AGE=0, **_mysql)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_PASSWORD_VALIDATORS = []   # default password is the student's name, so no strength rules

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing'

# ---------------- Email ----------------
if env('EMAIL_HOST_USER'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(env('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'SARS <no-reply@sars.local>')

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

ENABLE_SCHEDULER = env('ENABLE_SCHEDULER', '0') == '1'
