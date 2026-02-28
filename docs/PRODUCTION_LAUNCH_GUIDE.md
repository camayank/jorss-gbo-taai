# Production Launch Guide - Jorss-GBO Tax Platform

**Stack**: Render (hosting) + Neon (PostgreSQL) + Upstash (Redis)
**Cost**: $0/month (free tiers)
**Estimated Setup Time**: 20-30 minutes

---

## Prerequisites

Before starting, ensure you have:
- [ ] GitHub account (repository must be pushed to GitHub)
- [ ] Email address for service signups
- [ ] OpenAI API key (optional, for AI features)

---

## Step 1: Set Up Neon PostgreSQL (5 minutes)

### 1.1 Create Neon Account
1. Go to [neon.tech](https://neon.tech)
2. Click "Sign Up" (use GitHub for easier auth)
3. Select the **Free** plan

### 1.2 Create Database
1. Click "Create Project"
2. **Project name**: `jorss-gbo-production`
3. **Region**: Select closest to your users (e.g., `us-east-1`)
4. **Database name**: `taxplatform`
5. Click "Create Project"

### 1.3 Get Connection String
1. In your project dashboard, click "Connection Details"
2. Select "Connection string" tab
3. Copy the **pooled connection string** (looks like):
   ```
   postgresql://user:password@ep-xxx.us-east-1.aws.neon.tech/taxplatform?sslmode=require
   ```
4. **Save this** - you'll need it for Render

> **Note**: Neon's free tier includes:
> - 0.5 GB storage
> - 1 project
> - Auto-suspend after 5 min inactivity (wakes in ~5s)

---

## Step 2: Set Up Upstash Redis (5 minutes)

### 2.1 Create Upstash Account
1. Go to [upstash.com](https://upstash.com)
2. Click "Sign Up" (use GitHub for easier auth)
3. Select the **Free** plan

### 2.2 Create Redis Database
1. Click "Create Database"
2. **Name**: `jorss-gbo-cache`
3. **Region**: Same region as Neon (e.g., `us-east-1`)
4. **Type**: Regional (free tier)
5. Click "Create"

### 2.3 Get Connection Details
1. In your database dashboard, find "REST API" section
2. Copy the **UPSTASH_REDIS_REST_URL** and **UPSTASH_REDIS_REST_TOKEN**
3. Or use the standard Redis URL format:
   ```
   redis://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379
   ```
4. **Save this** - you'll need it for Render

> **Note**: Upstash free tier includes:
> - 10,000 commands/day
> - 256 MB storage
> - Pay-as-you-go beyond free tier

---

## Step 3: Push Code to GitHub (2 minutes)

If not already on GitHub:

```bash
cd /Users/rakeshanita/Desktop/MAYANK-ECOSYSTEM/08_Code-Technology/Jorss-Gbo

# Initialize git (if needed)
git init

# Add all files
git add .

# Commit
git commit -m "Prepare for production deployment"

# Create GitHub repo and push
# Option A: Use GitHub CLI
gh repo create jorss-gbo --public --push

# Option B: Manual
# 1. Create repo on github.com
# 2. git remote add origin https://github.com/YOUR_USERNAME/jorss-gbo.git
# 3. git push -u origin main
```

---

## Step 4: Deploy to Render (10 minutes)

### 4.1 Create Render Account
1. Go to [render.com](https://render.com)
2. Click "Get Started for Free"
3. Sign up with GitHub (recommended for auto-connect)

### 4.2 Create New Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repository (`jorss-gbo`)
3. Configure service:

| Setting | Value |
|---------|-------|
| **Name** | `jorss-gbo` |
| **Region** | Oregon (or closest to you) |
| **Branch** | `main` |
| **Runtime** | Python |
| **Build Command** | `chmod +x scripts/build.sh && ./scripts/build.sh` |
| **Start Command** | `PYTHONPATH=src gunicorn src.web.app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120 --keep-alive 5` |
| **Instance Type** | Free |

### 4.3 Configure Environment Variables

Click "Environment" and add these variables:

#### Required Variables

| Key | Value | Notes |
|-----|-------|-------|
| `APP_ENVIRONMENT` | `production` | |
| `ENVIRONMENT` | `production` | Used by WebSocket routes |
| `PYTHONPATH` | `src` | Required for internal imports |
| `AUTH_USE_DATABASE` | `true` | App will FATAL without this in production |
| `SESSION_STORAGE_TYPE` | `redis` | Redis-backed sessions |
| `APP_ENFORCE_HTTPS` | `true` | HTTPS enforcement |
| `APP_ENABLE_RATE_LIMITING` | `true` | Rate limiting |
| `DATABASE_URL` | `postgresql://...` | From Neon Step 1.3 |
| `REDIS_URL` | `rediss://...` | From Upstash Step 2.3 (note: `rediss://` for TLS) |
| `CORS_ORIGINS` | `https://yourdomain.com` | Your production domain(s), comma-separated |
| `APP_SECRET_KEY` | (generate) | See below |
| `JWT_SECRET` | (generate) | See below |
| `CSRF_SECRET_KEY` | (generate) | See below |
| `ENCRYPTION_MASTER_KEY` | (generate) | See below |
| `SSN_HASH_SECRET` | (generate) | See below |
| `AUTH_SECRET_KEY` | (generate) | See below |
| `PASSWORD_SALT` | (generate) | See below |
| `SERIALIZER_SECRET_KEY` | (generate) | See below |
| `AUDIT_HMAC_KEY` | (generate) | See below |

#### Generate Secrets

Run this locally to generate all secrets:

```bash
python -c "
import secrets
keys = ['APP_SECRET_KEY', 'JWT_SECRET', 'CSRF_SECRET_KEY',
        'ENCRYPTION_MASTER_KEY', 'SSN_HASH_SECRET', 'AUTH_SECRET_KEY',
        'SERIALIZER_SECRET_KEY', 'AUDIT_HMAC_KEY']
for key in keys:
    print(f'{key}={secrets.token_hex(32)}')
print(f'PASSWORD_SALT={secrets.token_hex(16)}')
"
```

Copy each generated value into Render's environment variables.

#### Optional Variables

| Key | Value | Notes |
|-----|-------|-------|
| `OPENAI_API_KEY` | `sk-...` | For AI features |
| `SENDGRID_API_KEY` | `SG.xxx` | For email notifications |
| `SENTRY_DSN` | `https://...` | For error tracking |
| `PLATFORM_NAME` | `Your Tax Platform` | Branding |
| `COMPANY_NAME` | `Your Company Name` | Branding |
| `SUPPORT_EMAIL` | `support@yourdomain.com` | Branding |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

#### Feature Flags

| Key | Value |
|-----|-------|
| `UNIFIED_FILING` | `true` |
| `DB_PERSISTENCE` | `true` |
| `NEW_LANDING` | `true` |
| `APP_ENABLE_CACHING` | `true` |
| `APP_ENABLE_BACKGROUND_TASKS` | `true` |
| `AI_CHAT_ENABLED` | `true` |
| `AI_SAFETY_CHECKS` | `true` |

### 4.4 Deploy

1. Click "Create Web Service"
2. Wait for build to complete (5-10 minutes first time)
3. Once deployed, you'll get a URL like: `https://jorss-gbo.onrender.com`

---

## Step 5: Verify Deployment (5 minutes)

### 5.1 Health Check
```bash
curl https://YOUR-APP.onrender.com/api/health
# Expected: {"status": "healthy"}
```

### 5.2 Test Landing Page
1. Open `https://YOUR-APP.onrender.com/landing`
2. Verify branding appears correctly
3. Click "Start Filing" to test flow

### 5.3 Test Database Connection
```bash
curl https://YOUR-APP.onrender.com/api/health/database
# Expected: {"status": "healthy", "database": "connected"}
```

---

## Post-Launch Checklist

### Immediate (Day 1)
- [ ] Verify all pages load correctly
- [ ] Test document upload flow
- [ ] Test tax calculation
- [ ] Monitor logs for errors (Render dashboard → Logs)
- [ ] Test on mobile device

### Week 1
- [ ] Set up custom domain (optional)
- [ ] Configure email notifications (SMTP)
- [ ] Monitor database usage (Neon dashboard)
- [ ] Monitor Redis usage (Upstash dashboard)
- [ ] Gather user feedback

### Month 1
- [ ] Review error logs
- [ ] Analyze performance metrics
- [ ] Consider upgrading from free tiers if needed
- [ ] Set up monitoring/alerting

---

## Troubleshooting

### App Won't Start

**Check build logs in Render dashboard:**
1. Go to your service → "Logs"
2. Look for error messages

**Common issues:**
- Missing environment variable → Add it in Environment tab
- Python version mismatch → Check `runtime.txt` says `python-3.11.11`
- Import error → Check all dependencies in `requirements.txt`

### Database Connection Failed

**Verify Neon connection:**
```bash
# Test from local machine
psql "YOUR_DATABASE_URL"
```

**Common issues:**
- Wrong connection string → Use "pooled" connection from Neon
- SSL required → Ensure `?sslmode=require` in URL
- Database sleeping → First request wakes it (~5s delay)

### Redis Connection Failed

**Verify Upstash connection:**
```bash
# Test with redis-cli
redis-cli -u "YOUR_REDIS_URL" PING
# Expected: PONG
```

**Common issues:**
- Wrong URL format → Use `redis://default:PASSWORD@HOST:PORT`
- Rate limited → Check Upstash dashboard for quota

### App Sleeping (Free Tier)

Render free tier sleeps after 15 min inactivity. First request takes ~30s.

**Solutions:**
- Accept the delay (normal for testing)
- Use a service like [UptimeRobot](https://uptimerobot.com) to ping every 10 min (keeps it awake)
- Upgrade to paid tier ($7/month for always-on)

---

## Cost Breakdown

| Service | Free Tier Limits | Paid Upgrade |
|---------|-----------------|--------------|
| **Render** | 750 hrs/month, sleeps after 15min | $7/month (Starter) |
| **Neon** | 0.5 GB, auto-suspend | $19/month (Pro) |
| **Upstash** | 10K commands/day | $0.20/100K commands |

**Total for testing**: $0/month
**Total for production**: ~$30-50/month

---

## Quick Reference

### URLs
- **App**: `https://YOUR-APP.onrender.com`
- **Health**: `https://YOUR-APP.onrender.com/api/health`
- **Landing**: `https://YOUR-APP.onrender.com/landing`

### Dashboards
- **Render**: [dashboard.render.com](https://dashboard.render.com)
- **Neon**: [console.neon.tech](https://console.neon.tech)
- **Upstash**: [console.upstash.com](https://console.upstash.com)

### Logs
```bash
# Render logs (in dashboard or)
render logs --service jorss-gbo

# Or view in Render dashboard → Your Service → Logs
```

### Redeploy
```bash
# Push to GitHub triggers auto-deploy
git push origin main

# Or manual redeploy in Render dashboard → "Manual Deploy"
```

---

## Next Steps

After successful deployment:

1. **Custom Domain**: Add your domain in Render → Settings → Custom Domains
2. **SSL**: Render provides free SSL automatically
3. **Monitoring**: Set up Sentry for error tracking (free tier available)
4. **Analytics**: Add Google Analytics or similar
5. **Backups**: Neon has automatic backups on free tier

---

**Congratulations!** Your Jorss-GBO Tax Platform is now live.
