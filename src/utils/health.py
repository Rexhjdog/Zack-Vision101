"""Health check and monitoring module."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

import discord

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health check status."""
    healthy: bool
    component: str
    message: str
    last_check: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'healthy': self.healthy,
            'component': self.component,
            'message': self.message,
            'last_check': self.last_check.isoformat(),
            'details': self.details
        }


class HealthChecker:
    """Health checker for monitoring bot components."""
    
    def __init__(
        self,
        bot: discord.Client,
        db=None,
        scheduler=None,
        max_check_age_seconds: int = 300  # 5 minutes
    ):
        self.bot = bot
        self.db = db
        self.scheduler = scheduler
        self.max_check_age = timedelta(seconds=max_check_age_seconds)
        self._last_health_check: Optional[datetime] = None
    
    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks.
        
        Returns:
            Dict with overall status and individual component statuses
        """
        self._last_health_check = datetime.now()
        
        checks = [
            self._check_discord(),
            self._check_database(),
            self._check_scheduler(),
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        # Filter out exceptions
        statuses = []
        for result in results:
            if isinstance(result, Exception):
                statuses.append(HealthStatus(
                    healthy=False,
                    component="unknown",
                    message=f"Check failed: {str(result)}",
                    last_check=datetime.now()
                ))
            else:
                statuses.append(result)
        
        overall_healthy = all(status.healthy for status in statuses)
        
        return {
            'healthy': overall_healthy,
            'timestamp': datetime.now().isoformat(),
            'checks': [status.to_dict() for status in statuses]
        }
    
    async def _check_discord(self) -> HealthStatus:
        """Check Discord connection health."""
        try:
            if not self.bot.is_ready():
                return HealthStatus(
                    healthy=False,
                    component='discord',
                    message='Bot is not ready',
                    last_check=datetime.now(),
                    details={'is_ready': False}
                )
            
            # Check latency
            latency = self.bot.latency
            healthy = latency < 1.0  # Consider unhealthy if latency > 1s
            
            return HealthStatus(
                healthy=healthy,
                component='discord',
                message=f'Connected with {latency*1000:.0f}ms latency',
                last_check=datetime.now(),
                details={
                    'is_ready': True,
                    'latency_ms': round(latency * 1000, 2),
                    'guilds': len(self.bot.guilds)
                }
            )
            
        except Exception as e:
            return HealthStatus(
                healthy=False,
                component='discord',
                message=f'Discord check failed: {str(e)}',
                last_check=datetime.now()
            )
    
    async def _check_database(self) -> HealthStatus:
        """Check database connection health."""
        if not self.db:
            return HealthStatus(
                healthy=False,
                component='database',
                message='Database not initialized',
                last_check=datetime.now()
            )
        
        try:
            # Try to get a simple count
            count = await self.db.get_product_count()
            
            return HealthStatus(
                healthy=True,
                component='database',
                message=f'Database connected with {count} products',
                last_check=datetime.now(),
                details={'product_count': count}
            )
            
        except Exception as e:
            return HealthStatus(
                healthy=False,
                component='database',
                message=f'Database check failed: {str(e)}',
                last_check=datetime.now()
            )
    
    async def _check_scheduler(self) -> HealthStatus:
        """Check scheduler health."""
        if not self.scheduler:
            return HealthStatus(
                healthy=False,
                component='scheduler',
                message='Scheduler not initialized',
                last_check=datetime.now()
            )
        
        try:
            if not self.scheduler.running:
                return HealthStatus(
                    healthy=False,
                    component='scheduler',
                    message='Scheduler is not running',
                    last_check=datetime.now(),
                    details={'running': False}
                )
            
            # Check if last check was recent enough
            last_check = self.scheduler._stats.last_check
            if last_check and (datetime.now() - last_check) > self.max_check_age:
                return HealthStatus(
                    healthy=False,
                    component='scheduler',
                    message=f'Last check was {(datetime.now() - last_check).seconds}s ago',
                    last_check=datetime.now(),
                    details={
                        'running': True,
                        'last_check': last_check.isoformat() if last_check else None,
                        'total_checks': self.scheduler._stats.total_checks
                    }
                )
            
            return HealthStatus(
                healthy=True,
                component='scheduler',
                message=f'Scheduler running with {self.scheduler._stats.total_checks} total checks',
                last_check=datetime.now(),
                details={
                    'running': True,
                    'total_checks': self.scheduler._stats.total_checks,
                    'successful_checks': self.scheduler._stats.successful_checks,
                    'failed_checks': self.scheduler._stats.failed_checks
                }
            )
            
        except Exception as e:
            return HealthStatus(
                healthy=False,
                component='scheduler',
                message=f'Scheduler check failed: {str(e)}',
                last_check=datetime.now()
            )
    
    def is_healthy(self) -> bool:
        """Quick check if all components are healthy.
        
        Returns:
            bool: True if all components are healthy
        """
        if not self._last_health_check:
            return False
        
        # Check if health check is recent
        if (datetime.now() - self._last_health_check) > self.max_check_age:
            return False
        
        # This is a synchronous check - for detailed status use check_all()
        return (
            self.bot.is_ready() and
            self.db is not None and
            self.scheduler is not None and
            self.scheduler.running
        )
