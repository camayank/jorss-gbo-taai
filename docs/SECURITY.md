# Security Features

This document outlines the security features implemented in the tax filing platform.

## Table of Contents

1. [Security Headers](#security-headers)
2. [Rate Limiting](#rate-limiting)
3. [CSRF Protection](#csrf-protection)
4. [Request Validation](#request-validation)
5. [Session Security](#session-security)
6. [Configuration](#configuration)

## Security Headers

All HTTP responses include comprehensive security headers:

### Headers Applied

- **Strict-Transport-Security (HSTS)**: Forces HTTPS for 1 year
- **X-Content-Type-Options**: Prevents MIME type sniffing
- **X-Frame-Options**: Prevents clickjacking (set to DENY)
- **X-XSS-Protection**: Enables browser XSS protection
- **Content-Security-Policy**: Restricts resource loading
- **Referrer-Policy**: Controls referrer information
- **Permissions-Policy**: Disables unused browser features

### Content Security Policy

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' https:;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

**Note**: `'unsafe-inline'` is enabled for scripts and styles to support inline templates. Consider migrating to nonce-based CSP for production.

## Rate Limiting

### Token Bucket Algorithm

- **Requests per minute**: 60
- **Burst size**: 20
- **Per-IP tracking**: Yes

### How It Works

1. Each IP gets a "bucket" with 20 tokens initially
2. Each request consumes 1 token
3. Tokens refill at 1 per second (60/minute)
4. Burst allows temporary spikes

### Exempt Paths

- `/health`
- `/metrics`
- `/static/*`

### Rate Limit Headers

```
X-RateLimit-Limit-Minute: 60
X-RateLimit-Limit-Hour: 1000
X-RateLimit-Remaining-Minute: 45
```

### Response on Rate Limit

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "detail": "Too many requests. Please try again later."
}
```

## CSRF Protection

### How It Works

1. Server generates CSRF token and stores in cookie
2. Client must include token in:
   - `X-CSRF-Token` header (recommended), OR
   - `csrf_token` form field

3. Server validates token on state-changing requests (POST, PUT, PATCH, DELETE)

### Safe Methods (No CSRF Check)

- GET
- HEAD
- OPTIONS
- TRACE

### Exempt Paths

- `/api/health` - Health checks
- `/api/webhook` - External webhooks
- `/api/chat` - Uses Bearer authentication
- `/api/sessions/check-active` - Read-only

### Bearer Auth Bypass

Requests with `Authorization: Bearer <token>` header skip CSRF validation.

### Token Generation

```python
# Server-side (Python)
from security.middleware import CSRFMiddleware

csrf = CSRFMiddleware(app, secret_key=SECRET_KEY)
token = csrf.generate_token()
```

### Token Usage (Client-side)

```javascript
// Include in request headers
fetch('/api/sessions/transfer-anonymous', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCsrfToken()  // From cookie or meta tag
  },
  body: JSON.stringify({ ... })
});
```

### Response on CSRF Failure

```http
HTTP/1.1 403 Forbidden

{
  "detail": "CSRF token missing"
}
```

## Request Validation

### Max Content Length

- Default: 50 MB (for tax document uploads)
- Configurable per environment

### Allowed Content Types

- `application/json`
- `application/x-www-form-urlencoded`
- `multipart/form-data`
- `text/plain`

### Validation Rules

1. **Content-Length Header**: Required for POST/PUT/PATCH
2. **Content-Type Header**: Must match allowed types
3. **Request Body Size**: Enforced before parsing

## Session Security

### Session Storage

- **Backend**: SQLite with encrypted fields
- **Cookie**: HttpOnly, SameSite=Lax
- **TTL**: 24 hours (configurable)

### Session Cookies

```
Set-Cookie: tax_session_id=<uuid>;
  HttpOnly;
  SameSite=Lax;
  Secure (in production);
  Max-Age=86400
```

### Anonymous Sessions

- Generated on first visit
- Can be transferred to authenticated user after login
- Tracked in `session_transfers` table

### Session Cleanup

Expired sessions are automatically cleaned up by the `/api/sessions/cleanup-expired` endpoint.

**Recommended**: Set up cron job to call this endpoint hourly:

```bash
# Add to crontab
0 * * * * curl -X POST http://localhost:8000/api/sessions/cleanup-expired
```

## Configuration

### Environment Variables

```bash
# Required in production
CSRF_SECRET_KEY=<64-character-hex-string>

# Optional
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=20
SESSION_TTL_HOURS=24
MAX_UPLOAD_SIZE_MB=50
```

### Generating Secret Keys

```bash
# CSRF secret
python -c "import secrets; print(secrets.token_hex(32))"
```

### Testing Security

```bash
# Test rate limiting
for i in {1..70}; do curl http://localhost:8000/api/health; done

# Test CSRF protection (should fail without token)
curl -X POST http://localhost:8000/api/sessions/transfer-anonymous \
  -H "Content-Type: application/json" \
  -d '{"anonymous_session_id":"test"}'

# Test with CSRF token (should succeed)
curl -X POST http://localhost:8000/api/sessions/transfer-anonymous \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"anonymous_session_id":"test"}'
```

## Security Checklist

### Before Production Deployment

- [ ] Set `CSRF_SECRET_KEY` environment variable
- [ ] Enable HTTPS (Strict-Transport-Security requires it)
- [ ] Review Content-Security-Policy (consider nonce-based CSP)
- [ ] Set up session cleanup cron job
- [ ] Configure rate limiting for production traffic
- [ ] Review exempt paths (minimize API endpoints without CSRF)
- [ ] Enable secure cookies (`Secure` flag)
- [ ] Configure CORS allowed origins
- [ ] Review and test authentication flows
- [ ] Audit file upload security (virus scanning, type validation)
- [ ] Enable request logging for security monitoring
- [ ] Set up intrusion detection (fail2ban, CloudFlare, etc.)

### Ongoing Monitoring

- Monitor rate limit violations (check logs for 429 responses)
- Monitor CSRF failures (check logs for 403 with "CSRF" message)
- Review session cleanup logs (ensure expired sessions are removed)
- Monitor for unusual patterns (brute force, enumeration)
- Regular security audits and penetration testing

## Common Security Scenarios

### User Starts Filing Anonymously, Then Logs In

1. User starts filing → anonymous session created
2. User logs in → session transferred to user account
3. Session persists with user_id

### API Authentication

- Bearer tokens exempt from CSRF (for API clients)
- Session cookies still used for web interface
- Both authentication methods supported

### Cross-Site Request Attacks

- CSRF middleware blocks state-changing requests without valid token
- SameSite=Lax cookies provide additional protection
- Referrer policy prevents leaking sensitive URLs

## References

- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Secure Headers](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
- [MDN Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [RFC 6265 - HTTP State Management](https://tools.ietf.org/html/rfc6265)
