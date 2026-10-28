# Django web client

## Local development

FastAPI runs on `8000`, so Django uses `8001`.

```bat
copy .env.example .env
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

`DEBUG=True` is the default for local development. Secure cookies default to
off in DEBUG, so login works over local HTTP.

## Production

- Set `DEBUG=False` and configure `ALLOWED_HOSTS`.
- Keep `COOKIE_SECURE` unset (or `True`) behind HTTPS. The default is secure
  whenever `DEBUG=False`. Set it to `False` only for a local HTTP run with
  `DEBUG=False`.
- Run `python manage.py collectstatic --noinput`. WhiteNoise serves the
  collected files from `STATIC_ROOT` (`web/staticfiles/`); no separate static
  web server is required.
- Terminate HTTPS at the reverse proxy; Django's secure-cookie settings assume
  HTTPS outside DEBUG.
