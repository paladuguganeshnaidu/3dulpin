# Security

## Summary

- **Passwords**: PBKDF2-HMAC-SHA256 (260k iterations), salted, constant-time
  comparison. No bcrypt dependency needed.
- **Tokens**: JWT (HS256), subject + role claims, expiry from env; secret from
  `JWT_SECRET_KEY`.
- **RBAC**: `viewer` (browse only) / `surveyor` (create, verify AI candidates,
  submit) / `admin` (review/approve, manage users, audit). Server-side guards on
  every protected endpoint.
- **Uploads**: size limit (`MAX_UPLOAD_MB`), allowed/recognized extensions,
  sanitized filenames (path traversal protection), files stored under
  `data/uploads/<token>/`.
- **Errors**: structured `{detail}`; production never leaks stack traces
  (global handler + `APP_ENV=production`).
- **SQL**: parameterized through SQLAlchemy (no string-built user SQL).
- **CORS**: allow-list from `CORS_ORIGINS`.
- **Secrets**: `.env` never committed (`.gitignore`); `.env.example` has only
  placeholders; CI has no secrets.
- **Audit**: server-written `audit_logs` (login, upload, geometry create/modify,
  AI analysis, validation, submission, approval, rejection). Users cannot edit
  audit rows.

## Explicit boundaries

The LLM assistant cannot run arbitrary SQL, shell or filesystem operations; it
calls a fixed set of read-only tools. No LLM/ML output can auto-approve a legal
record — approval is a human admin action.

## Production checklist

1. Generate a strong `JWT_SECRET_KEY` (e.g. `python -c "import secrets;print(secrets.token_urlsafe(48))"`).
2. Set `APP_ENV=production` and `CORS_ORIGINS` to the real origin.
3. Use PostGIS with least-privilege DB credentials.
4. Terminate TLS at the proxy.
5. Optional: rate limiting / auth throttling behind the proxy for public deploys.
