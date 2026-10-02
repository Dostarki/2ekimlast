# Admin authentication regression checklist

Scope: existing password-only `/api/admin` protocol, not new registration or OAuth.

1. Read `memory/test_credentials.md`. External tests obtain `TEST_ADMIN_PASSWORD` from the environment or ignored `backend/.env.test`; never put a fallback password in source.
2. Use isolated MongoDB collections/databases or generated unit fixtures for lockout, expiry and missing-account tests. Do not reset or lock out the live operator.
3. Verify login → me → refresh → logout; status codes and `{role: admin}` response unchanged. Two sessions remain independent; revoked sessions cannot refresh.
4. Check cookies `admin_access` (900s) and `admin_refresh` (604800s): Secure, HttpOnly, SameSite=Strict, Path=/api/admin. Refresh renews only access; deletion uses matching cookie attributes.
5. Reject missing/expired/tampered JWTs, missing exp/sub/type/sid, incorrect subject/type, nonexistent/expired Mongo sessions. Only HS256 is accepted.
6. First five wrong passwords return 401, sixth attempt 429 with Retry-After, including correct-password retry while locked. Successful login clears attempts. UTF-8 passwords over 72 bytes are rejected without a bcrypt exception.
7. Inspect operator/session/attempt indexes and TTL; seed behavior remains unchanged. Passwords are hashed using bcrypt and JWT secrets loaded from environment; do not rotate production credentials in this refactor.
8. Origin validation is intentionally a no-op under the existing user choice. Do not reintroduce origin/IP/user-agent restrictions while refactoring.

Test tools live in `/tmp/lastzhood-tests`, not the 46-package production runtime. Browser/API checks use `REACT_APP_BACKEND_URL`; backend DB connections use existing environment configuration. Never print hashes, passwords, session cookies or secrets in test output.