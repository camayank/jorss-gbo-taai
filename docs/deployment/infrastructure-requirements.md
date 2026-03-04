# Infrastructure Requirements

## Current Stack
| Service | Provider | Tier | Limitation |
|---------|----------|------|------------|
| Compute | Render | Free | Auto-suspends after 15 min inactivity; 750 hrs/month |
| Database | Neon PostgreSQL | Free | 0.5 GB storage, 1 compute endpoint |
| Cache/Queue | Upstash Redis | Free | 10,000 commands/day, 256 MB |
| Email | SendGrid | Free | 100 emails/day |
| Monitoring | Sentry | Free | 5,000 events/month |
| AI | OpenAI | Pay-as-you-go | Rate limits per tier |

## Free Tier Limitations

### Render (Compute)
- **Auto-suspend:** Service sleeps after 15 minutes of inactivity. First request after sleep takes 30-60 seconds (cold start).
- **Impact:** Poor UX for first visitor after idle period. Celery workers cannot run continuously.
- **Upgrade trigger:** When consistent traffic exceeds 1 request/15 min or background tasks are needed.

### Neon (Database)
- **Storage:** 0.5 GB total. Current schema + seed data uses ~50 MB.
- **Compute:** Single endpoint, auto-scales but limited.
- **Impact:** Storage fills with ~500 active clients × 5 tax returns each.
- **Upgrade trigger:** When data exceeds 400 MB or need for read replicas.

### Upstash (Redis)
- **Commands:** 10,000/day. Each page view uses 3-5 commands (CSRF, session, cache).
- **Impact:** Rate limiting stops working at ~2,000-3,000 page views/day.
- **Upgrade trigger:** When daily command usage consistently exceeds 8,000.

## Tier Recommendations

### Starter ($25/month) — 1-10 active users
- Render Starter: $7/mo (no auto-suspend, 512 MB RAM)
- Neon Launch: $0 (0.5 GB included, pay for compute)
- Upstash Pay-as-you-go: ~$3/mo (200K commands/day)
- SendGrid Free: $0 (100 emails/day sufficient)
- Sentry Team: $0-15/mo (50K events)
- **Total: ~$25/month**

### Growth ($75/month) — 10-100 active users
- Render Standard: $25/mo (2 GB RAM, always-on)
- Neon Scale: $19/mo (10 GB storage, autoscaling)
- Upstash Pro: $10/mo (unlimited commands)
- SendGrid Essentials: $20/mo (100K emails/month)
- Sentry Team: $0 (covered in free tier events)
- **Total: ~$75/month**

### Production ($200/month) — 100-1,000 active users
- Render Pro: $85/mo (4 GB RAM, multiple instances)
- Neon Business: $49/mo (50 GB, dedicated compute)
- Upstash Enterprise: $30/mo (dedicated cluster)
- SendGrid Pro: $30/mo (1.5M emails/month)
- Sentry Business: $26/mo (unlimited events)
- **Total: ~$220/month**

## Migration Steps

### Render Free → Starter
1. Upgrade plan in Render dashboard
2. No code changes required
3. Service stops auto-suspending immediately

### Neon Free → Launch/Scale
1. Upgrade in Neon console
2. No DATABASE_URL change needed
3. Storage limit increases automatically

### Upstash Free → Pay-as-you-go
1. Upgrade in Upstash console
2. No REDIS_URL change needed
3. Command limits increase automatically

### Adding Celery Workers (any paid tier)
1. Create new Render Background Worker service
2. Set same environment variables as web service
3. Start command: `celery -A tasks.celery_app worker --loglevel=info`
4. Add Celery Beat service for scheduled tasks

## Monitoring Thresholds
- **Database storage:** Alert at 80% capacity
- **Redis commands:** Alert at 80% daily limit
- **Response time:** Alert if p95 > 2 seconds
- **Error rate:** Alert if > 1% of requests return 5xx
- **Celery queue depth:** Alert if > 100 pending tasks
