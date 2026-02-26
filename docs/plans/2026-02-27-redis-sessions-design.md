# Redis-Backed Shared Sessions for IntelligentChatEngine

## Problem

IntelligentChatEngine stores sessions in a per-process Python dict. With multiple uvicorn workers, requests route randomly, causing users to lose sessions mid-conversation.

## Design

**L1 cache (in-memory dict)** + **L2 store (Redis)** with SQLite fallback.

### Architecture

- L1: `self.sessions` dict stays for fast hot-path reads (~0ms)
- L2: Redis via existing `RedisSessionPersistence` (~1ms per call)
- Fallback: SQLite via existing `SessionPersistence` if Redis unavailable

### Changes

1. `IntelligentChatEngine.__init__` — initialize with async Redis persistence
2. `_save_session_to_db` / `_load_session_from_db` — make async, use Redis persistence
3. `_cleanup_stale_sessions` — make async, persist to Redis before eviction
4. Docker-compose — remove `profiles: [with-redis]` so Redis starts by default
5. `.env.example` — document `SESSION_STORAGE_TYPE=redis`

### What stays the same

- L1 in-memory cache and eviction logic
- Serialization/deserialization methods
- Session token auth layer
- All endpoint signatures

### Why keep L1 cache

During a chat turn, `get_or_create_session` is called multiple times. The L1 cache avoids repeated Redis round-trips for the same session within a single request.
