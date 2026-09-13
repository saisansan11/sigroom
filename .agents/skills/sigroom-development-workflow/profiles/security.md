# Security Profile

- Preserve least privilege and server-side authorization.
- Never rely on hidden buttons or template conditions as the security boundary.
- Treat public endpoints, student links, QR links, exports, admin paths, and media URLs as separate exposure surfaces.
- Review privacy leakage in rendered HTML, logs, URLs, CSV/export output, and error messages.
- Keep CSRF/session/cookie/proxy configuration aligned with the active deployment architecture.
- Do not weaken tests, headers, permissions, or validation to work around local environment problems.
- Security changes require targeted negative tests plus full regression and explicit rollback notes.
