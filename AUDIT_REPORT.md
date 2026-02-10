# Comprehensive Project Audit Report
## Pokemon/One Piece TCG Stock Alert Bot

**Date:** 2026-02-09  
**Repository:** https://github.com/Rexhjdog/Zack-Vision101  
**Scope:** Full codebase audit focusing on security, reliability, performance, and best practices

---

## Executive Summary

The project is a functional Discord bot for monitoring TCG booster box stock across 5 Melbourne retailers. However, **several critical issues** have been identified that need immediate attention before production deployment.

**Risk Level:** 🔴 HIGH - Multiple blocking issues prevent safe production use

---

## 1. CRITICAL ISSUES (Must Fix Immediately)

### 1.1 Broken Scraper Selectors (HIGH RISK)
**Files:** All scraper files (`eb_games.py`, `jb_hifi.py`, `target_au.py`, `big_w.py`, `kmart.py`)

**Issue:** The CSS selectors used for scraping are generic placeholder selectors that likely don't match the actual retailer's HTML structure.

**Examples of problematic selectors:**
```python
# EB Games
soup.find_all('div', class_='product-item')  # May not exist
soup.find('a', class_='product-link')        # May not exist
soup.find('span', class_='price')            # May not exist

# JB Hi-Fi
soup.find_all('div', class_='product-tile')  # May not exist
```

**Impact:** Scrapers will return zero results, making the bot useless.

**Fix:** You MUST manually inspect each retailer's website HTML and update selectors accordingly.

### 1.2 No Rate Limiting Protection (HIGH RISK)
**Files:** `scheduler.py`, `scrapers/base.py`

**Issue:** 
- No delays between requests to the same retailer
- 2-minute check interval is aggressive and may trigger IP bans
- No exponential backoff on failures
- Missing `robots.txt` compliance check

**Current Behavior:**
```python
# scheduler.py:77-82
pokemon_products = await scraper.search_products('pokemon booster box')
onepiece_products = await scraper.search_products('one piece booster box')
# These run with zero delay between them!
```

**Impact:** 
- IP bans from retailers
- Legal/ToS violations
- Bot becomes non-functional

**Fix:** 
```python
# Add delay between requests
await asyncio.sleep(random.uniform(2, 5))  # 2-5 second delay
```

### 1.3 No Anti-Detection Measures (MEDIUM-HIGH RISK)
**Files:** `scrapers/base.py`

**Issue:** While User-Agent rotation exists, several other fingerprinting vectors are exposed:
- Missing proper cookie handling
- No session persistence
- Missing common headers (Referer, DNT, etc.)
- No JavaScript rendering (many sites use JS frameworks)

**Fix:** Consider using playwright/selenium for JavaScript-heavy sites.

### 1.4 Database Race Conditions (MEDIUM RISK)
**Files:** `database.py`

**Issue:** SQLite is being used without proper locking mechanisms for concurrent access. The scheduler runs async tasks that could conflict.

**Fix:** Use proper connection pooling or switch to PostgreSQL for production.

---

## 2. SECURITY ISSUES

### 2.1 SQL Injection Risk (MEDIUM RISK)
**File:** `database.py:162-168`

**Issue:** String formatting used in SQL query:
```python
cursor.execute('''
    SELECT a.*, p.name, p.retailer, p.url 
    FROM alerts a
    JOIN products p ON a.product_id = p.id
    WHERE a.timestamp > datetime('now', '-{} hours')
    ORDER BY a.timestamp DESC
'''.format(hours))
```

**Fix:** Use parameterized queries:
```python
cursor.execute('''
    SELECT a.*, p.name, p.retailer, p.url 
    FROM alerts a
    JOIN products p ON a.product_id = p.id
    WHERE a.timestamp > datetime('now', '-' || ? || ' hours')
    ORDER BY a.timestamp DESC
''', (hours,))
```

### 2.2 Missing Input Validation (MEDIUM RISK)
**Files:** `bot.py:38-66`, All slash commands

**Issue:** URLs from users are not validated before being stored/used:
```python
@bot.tree.command(name='track', description='Add a product URL to monitor')
async def track(interaction: discord.Interaction, url: str, name: Optional[str] = None):
    # No URL validation!
    product_id = f"user_{hash(url) % 10000000}"
```

**Impact:** 
- SSRF vulnerabilities
- Malicious URLs could be stored
- Potential security exploits

**Fix:**
```python
from urllib.parse import urlparse

def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    allowed_domains = ['ebgames.com.au', 'jbhifi.com.au', ...]
    return parsed.netloc in allowed_domains
```

### 2.3 Token Exposure Risk (LOW-MEDIUM RISK)
**Files:** `.env.example`, `config.py`

**Issue:** 
- `.env.example` shows the format but isn't in `.gitignore` explicitly
- No warnings about keeping tokens secret
- Token validation doesn't check format

**Fix:** Add pre-commit hooks to prevent token commits.

### 2.4 No Request Timeout on Discord Operations (LOW RISK)
**Files:** `bot.py:263`

**Issue:** `@everyone` ping could fail and block indefinitely:
```python
await channel.send("@everyone 🚨 STOCK ALERT!", embed=embed)
```

**Fix:** Add timeout:
```python
await asyncio.wait_for(
    channel.send("@everyone 🚨 STOCK ALERT!", embed=embed),
    timeout=10.0
)
```

---

## 3. RELIABILITY ISSUES

### 3.1 No Alert Deduplication Logic (MEDIUM RISK)
**Files:** `scheduler.py:108-125`

**Issue:** Alert cooldown is configured (5 minutes) but never implemented:
```python
# config.py:126
ALERT_COOLDOWN = 300  # 5 minutes between alerts for same product

# But never used in scheduler.py!
```

**Impact:** Same product could trigger multiple alerts if stock fluctuates.

**Fix:** Check last alert time before sending.

### 3.2 Fragile Stock Detection (MEDIUM RISK)
**Files:** All scrapers

**Issue:** Stock detection relies on simple text matching:
```python
stock_text = stock_elem.text.lower()
in_stock = 'in stock' in stock_text or 'available' in stock_text
```

**Problems:**
- Doesn't handle "Pre-order", "Backorder", "Coming Soon"
- No quantity checking
- Doesn't handle "Low Stock" warnings
- Different retailers use different terminology

**Fix:** Implement proper state machine for stock statuses.

### 3.3 No Retry Logic (MEDIUM RISK)
**Files:** All scrapers

**Issue:** Single network failure causes complete scraper failure for that retailer.

**Current:**
```python
try:
    async with self.session.get(search_url, timeout=30) as response:
        # ...
except Exception as e:
    print(f"Error searching EB Games: {e}")
    return products  # Empty!
```

**Fix:** Implement exponential backoff retry:
```python
for attempt in range(3):
    try:
        # ... request ...
        break
    except Exception as e:
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)
        else:
            raise
```

### 3.4 Missing Error Context (LOW RISK)
**Files:** All scrapers

**Issue:** Errors are logged without context:
```python
except Exception as e:
    print(f"Error searching EB Games: {e}")
```

**Fix:** Include stack traces and request details:
```python
import traceback
except Exception as e:
    print(f"Error searching EB Games: {e}")
    print(traceback.format_exc())
```

---

## 4. CODE QUALITY ISSUES

### 4.1 Inconsistent Method Naming (LOW RISK)
**File:** `scrapers/base.py:56-93`

**Issue:** Method `_is_tcgp_product` is confusing - should be `_is_booster_box` now.

### 4.2 Magic Numbers (LOW RISK)
**Files:** Throughout codebase

**Issues:**
```python
timeout=30  # Why 30?
[:100]      # Why 100 characters?
[:16]       # Why 16 chars for ID?
MAX_ALERTS_PER_HOUR = 50  # Never enforced
```

**Fix:** Make constants with explanations.

### 4.3 Unused Imports (LOW RISK)
**Files:** 
- `requirements.txt`: `selenium`, `asyncio-mqtt`, `cloudscraper`, `fake-useragent`, `lxml`, `apscheduler` - not used
- `scrapers/eb_games.py`: `import re` - not used
- `database.py`: `import json` - not used

### 4.4 Circular Import Risk (LOW RISK)
**Files:** `scheduler.py:158`, `bot.py:227`

**Issue:**
```python
# scheduler.py
from bot import send_stock_alert

# bot.py
from scheduler import StockScheduler
```

While not currently causing issues, this is fragile.

**Fix:** Use dependency injection or event system.

### 4.5 Dead Code (LOW RISK)
**Files:** `scheduler.py:163-168`

**Issue:** `force_check()` exists but isn't exposed via Discord command.

### 4.6 No Type Safety on Discord Interactions (LOW RISK)
**Files:** `bot.py`

**Issue:** No validation that `interaction.channel_id` exists before using it.

---

## 5. ARCHITECTURE ISSUES

### 5.1 Monolithic Scraper Design (MEDIUM RISK)
**Issue:** Each scraper duplicates parsing logic. Changes to one often need to be replicated to all.

**Fix:** Create shared parsing utilities.

### 5.2 No Separation of Concerns (MEDIUM RISK)
**Issue:** Discord bot logic mixed with business logic in `bot.py`.

**Fix:** Separate into:
- `bot/` - Discord interface
- `services/` - Business logic
- `scrapers/` - Data extraction
- `models/` - Data structures

### 5.3 No Health Check Endpoint (MEDIUM RISK)
**Issue:** No way to verify bot is running properly without checking Discord.

**Fix:** Add HTTP health check or status command.

### 5.4 Database Schema Limitations (LOW RISK)
**Issue:** 
- No indexing on frequently queried columns
- No data retention policy (database will grow indefinitely)
- No migration system

---

## 6. PERFORMANCE ISSUES

### 6.1 Inefficient Database Queries (MEDIUM RISK)
**Files:** `database.py:109-115`

**Issue:** Loading ALL products into memory:
```python
def get_all_products(self) -> List[Product]:
    cursor.execute('SELECT * FROM products')  # Loads everything!
    rows = cursor.fetchall()
```

**Impact:** As database grows, this becomes slow.

**Fix:** Add pagination and filtering.

### 6.2 Synchronous File Operations in Async Code (MEDIUM RISK)
**Files:** `database.py`

**Issue:** SQLite operations block the event loop:
```python
with sqlite3.connect(self.db_path) as conn:
    # This blocks all other async operations!
```

**Fix:** Use `aiosqlite` for async database operations.

### 6.3 Memory Leak Potential (LOW RISK)
**Files:** `scheduler.py:40`

**Issue:** Task created but never stored/cancelled:
```python
asyncio.create_task(self._monitoring_loop())
```

**Fix:** Store task reference for proper cleanup.

### 6.4 No Connection Pooling (LOW RISK)
**Files:** `scrapers/base.py`

**Issue:** New session created for each scraper use:
```python
async with scraper:  # Creates new session
    # ... do work ...
# Session closed
```

**Fix:** Reuse sessions with proper pooling.

---

## 7. TESTING & MONITORING GAPS

### 7.1 No Unit Tests (HIGH RISK)
**Issue:** Zero test coverage for critical business logic.

**Fix:** Add pytest suite with:
- Mock HTML fixtures for each retailer
- Database operation tests
- Discord command tests

### 7.2 No Integration Tests (HIGH RISK)
**Issue:** No end-to-end testing of the scraping pipeline.

### 7.3 No Monitoring/Metrics (MEDIUM RISK)
**Issue:** No visibility into:
- Scraper success/failure rates
- Alert volume
- Database size
- Response times

**Fix:** Add Prometheus metrics or similar.

### 7.4 No Logging Framework (MEDIUM RISK)
**Issue:** Using `print()` instead of proper logging:
```python
print(f"🚨 STOCK ALERT: {product.name} at {product.retailer}")
```

**Fix:** Use Python's `logging` module with proper levels and handlers.

---

## 8. USER EXPERIENCE ISSUES

### 8.1 Poor Error Messages (MEDIUM RISK)
**Files:** `bot.py`

**Issue:** Generic error messages for users:
```python
except Exception as e:
    await interaction.response.send_message(
        f"❌ Error adding product: {str(e)}",
        ephemeral=True
    )
```

**Fix:** User-friendly error messages with actionable steps.

### 8.2 No Command Validation (LOW RISK)
**Files:** `bot.py:183-196`

**Issue:** `/search` command does nothing:
```python
@bot.tree.command(name='search', description='Search for products across all retailers')
async def search(interaction: discord.Interaction, query: str):
    await interaction.response.send_message(
        f"🔍 Searching for '{query}' across all retailers...",
        ephemeral=True
    )
    
    # This would trigger an immediate search
    # Implementation depends on your scraper setup
    await interaction.followup.send(
        "Search functionality is running in the background. Check back soon!",
        ephemeral=True
    )
```

### 8.3 No Progress Indicators (LOW RISK)
**Issue:** Long operations give no feedback (e.g., manual search).

### 8.4 Alert Fatigue Risk (LOW RISK)
**Issue:** Every in-stock alert sends `@everyone` - could annoy users.

**Fix:** Add alert throttling or per-user preferences.

---

## 9. DOCUMENTATION ISSUES

### 9.1 Incomplete Setup Instructions (MEDIUM RISK)
**Files:** `README.md`

**Missing:**
- Discord bot permission setup details
- Required OAuth2 scopes
- Channel ID retrieval steps
- Python version requirements
- Troubleshooting common issues

### 9.2 No Architecture Documentation (LOW RISK)
**Issue:** No diagrams or explanations of how components interact.

### 9.3 No API Documentation (LOW RISK)
**Issue:** No documentation of the data models or scraper interfaces.

---

## 10. DEPLOYMENT ISSUES

### 10.1 No Docker Support (MEDIUM RISK)
**Issue:** No containerization for easy deployment.

**Fix:** Add Dockerfile and docker-compose.yml.

### 10.2 No Process Management (MEDIUM RISK)
**Issue:** No systemd service, supervisor config, or process manager.

### 10.3 No Environment Validation (MEDIUM RISK)
**Files:** `bot.py:266-269`

**Current:**
```python
if not DISCORD_TOKEN:
    print("❌ DISCORD_TOKEN not set! Please create a .env file with your bot token.")
    return
```

**Missing:**
- Channel ID validation
- Token format validation
- Database connectivity check

### 10.4 No Graceful Shutdown (MEDIUM RISK)
**Files:** `bot.py`

**Issue:** No handling of SIGINT/SIGTERM for clean shutdown:
- Scrapers may be mid-request
- Database writes incomplete
- Discord connection not closed properly

**Fix:**
```python
import signal

async def shutdown(signal, loop):
    # Close scrapers
    # Close database
    # Close Discord
    
for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(sig, loop)))
```

---

## 11. RECOMMENDED PRIORITY ORDER

### Phase 1: Critical (Before Any Use)
1. ✅ Fix scraper selectors by testing against real sites
2. ✅ Add rate limiting and delays between requests
3. ✅ Fix SQL injection vulnerability
4. ✅ Add URL validation

### Phase 2: High Priority (Before Production)
5. Implement alert cooldown/deduplication
6. Add retry logic with exponential backoff
7. Switch to aiosqlite for async database
8. Add comprehensive error handling

### Phase 3: Medium Priority (Within First Week)
9. Add unit tests
10. Implement proper logging
11. Add Docker support
12. Add graceful shutdown

### Phase 4: Nice to Have
13. Add monitoring/metrics
14. Implement health checks
15. Add data retention policies
16. Improve documentation

---

## 12. SPECIFIC CODE RECOMMENDATIONS

### 12.1 Replace SQLite with PostgreSQL
For production use, SQLite will have concurrency issues. Use PostgreSQL with asyncpg.

### 12.2 Implement Circuit Breaker Pattern
Prevent cascading failures when a retailer goes down:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failures = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
```

### 12.3 Add Product Normalization
Prevent duplicate products from different URLs:
```python
def normalize_product(name: str, retailer: str) -> str:
    # Normalize set names, remove retailer-specific text, etc.
    pass
```

### 12.4 Implement Webhook Alternative
For reliability, also support webhooks as backup notification method.

---

## 13. COMPLIANCE & LEGAL

### 13.1 Terms of Service Compliance
**Issue:** Web scraping may violate retailer ToS.

**Recommendation:**
- Check each retailer's robots.txt
- Review their API offerings
- Consider reaching out for permission
- Implement respectful crawling (delays, off-peak hours)

### 13.2 Data Privacy
**Issue:** Storing Discord user IDs in database.

**Recommendation:** Add privacy policy and data retention notice.

---

## 14. CONCLUSION

The project has a solid foundation and good structure, but **is not ready for production use** due to:

1. **Non-functional scrapers** (placeholders instead of real selectors)
2. **Security vulnerabilities** (SQL injection, SSRF)
3. **No rate limiting** (will get banned)
4. **Missing critical features** (alert deduplication, error recovery)

**Estimated Time to Production Ready:** 2-3 weeks of focused development

**Confidence Level:** Medium - The architecture is sound, but implementation details need significant work.

---

## 15. IMMEDIATE ACTION ITEMS

1. **Test each scraper manually** against real websites
2. **Add minimum 5-second delays** between requests
3. **Fix SQL injection** in database.py
4. **Add URL validation** to /track command
5. **Implement alert cooldown** logic
6. **Add comprehensive logging**
7. **Write basic unit tests**
8. **Add retry logic** to all network operations

---

**Auditor:** AI Code Review  
**Confidence:** High  
**Risk Assessment:** Critical issues must be addressed before deployment
