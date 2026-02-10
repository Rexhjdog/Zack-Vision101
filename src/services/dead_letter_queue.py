"""Dead letter queue for failed alerts."""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.services.database import Database
from src.models.product import StockAlert, AlertType

logger = logging.getLogger(__name__)


@dataclass
class FailedAlert:
    """Represents a failed alert in the dead letter queue."""
    id: Optional[int]
    product_id: str
    alert_type: AlertType
    timestamp: datetime
    error_message: str
    retry_count: int
    last_retry: Optional[datetime]
    resolved: bool
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'product_id': self.product_id,
            'alert_type': self.alert_type.value,
            'timestamp': self.timestamp.isoformat(),
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'last_retry': self.last_retry.isoformat() if self.last_retry else None,
            'resolved': self.resolved
        }


class DeadLetterQueue:
    """Queue for handling failed alerts with retry logic."""
    
    def __init__(self, db: Database, max_retries: int = 3, retry_delay_minutes: int = 5):
        self.db = db
        self.max_retries = max_retries
        self.retry_delay = timedelta(minutes=retry_delay_minutes)
    
    async def add_failed_alert(
        self,
        alert: StockAlert,
        error_message: str
    ) -> int:
        """Add a failed alert to the dead letter queue.
        
        Args:
            alert: The alert that failed
            error_message: Error message describing the failure
            
        Returns:
            ID of the failed alert record
        """
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO failed_alerts 
                (product_id, alert_type, error_message, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (
                    alert.product.id,
                    alert.alert_type.value,
                    error_message,
                    datetime.now().isoformat()
                )
            )
            
            failed_id = cursor.lastrowid
            logger.warning(
                f"Alert failed and added to DLQ [ID: {failed_id}]: {error_message}"
            )
            return failed_id
    
    async def get_retryable_alerts(self) -> List[FailedAlert]:
        """Get alerts that are ready for retry.
        
        Returns:
            List of failed alerts ready for retry
        """
        cutoff_time = (datetime.now() - self.retry_delay).isoformat()
        
        async with self.db._connection.execute(
            """
            SELECT * FROM failed_alerts 
            WHERE resolved = 0 
            AND retry_count < ?
            AND (last_retry IS NULL OR last_retry < ?)
            ORDER BY timestamp ASC
            """,
            (self.max_retries, cutoff_time)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_failed_alert(row) for row in rows]
    
    async def increment_retry(self, failed_id: int) -> None:
        """Increment retry count for a failed alert.
        
        Args:
            failed_id: ID of the failed alert
        """
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE failed_alerts 
                SET retry_count = retry_count + 1, last_retry = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), failed_id)
            )
            logger.info(f"Incremented retry count for failed alert {failed_id}")
    
    async def mark_resolved(self, failed_id: int) -> None:
        """Mark a failed alert as resolved.
        
        Args:
            failed_id: ID of the failed alert
        """
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE failed_alerts SET resolved = 1 WHERE id = ?",
                (failed_id,)
            )
            logger.info(f"Marked failed alert {failed_id} as resolved")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics.
        
        Returns:
            Dictionary with DLQ statistics
        """
        async with self.db._connection.execute(
            "SELECT COUNT(*) FROM failed_alerts WHERE resolved = 0"
        ) as cursor:
            pending = (await cursor.fetchone())[0]
        
        async with self.db._connection.execute(
            "SELECT COUNT(*) FROM failed_alerts WHERE resolved = 1"
        ) as cursor:
            resolved = (await cursor.fetchone())[0]
        
        async with self.db._connection.execute(
            """
            SELECT COUNT(*) FROM failed_alerts 
            WHERE resolved = 0 AND retry_count >= ?
            """,
            (self.max_retries,)
        ) as cursor:
            exhausted = (await cursor.fetchone())[0]
        
        return {
            'pending': pending,
            'resolved': resolved,
            'exhausted': exhausted,
            'total': pending + resolved
        }
    
    async def cleanup_old(self, days: int = 30) -> int:
        """Remove old resolved alerts.
        
        Args:
            days: Age in days to cleanup
            
        Returns:
            Number of records deleted
        """
        cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM failed_alerts WHERE resolved = 1 AND timestamp < ?",
                (cutoff_time,)
            )
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old resolved alerts from DLQ")
            return deleted
    
    def _row_to_failed_alert(self, row) -> FailedAlert:
        """Convert database row to FailedAlert."""
        return FailedAlert(
            id=row[0],
            product_id=row[1],
            alert_type=AlertType(row[2]),
            timestamp=datetime.fromisoformat(row[3]),
            error_message=row[4],
            retry_count=row[5],
            last_retry=datetime.fromisoformat(row[6]) if row[6] else None,
            resolved=bool(row[7])
        )


class AlertRetryManager:
    """Manages retrying failed alerts."""
    
    def __init__(
        self,
        dlq: DeadLetterQueue,
        send_callback,
        check_interval: int = 300  # 5 minutes
    ):
        self.dlq = dlq
        self.send_callback = send_callback
        self.check_interval = check_interval
        self._retry_task = None
        self.running = False
    
    async def start(self):
        """Start the retry manager."""
        self.running = True
        self._retry_task = asyncio.create_task(self._retry_loop())
        logger.info("Alert retry manager started")
    
    async def stop(self):
        """Stop the retry manager."""
        self.running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        logger.info("Alert retry manager stopped")
    
    async def _retry_loop(self):
        """Main retry loop."""
        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._process_retries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retry loop: {e}", exc_info=True)
    
    async def _process_retries(self):
        """Process retryable alerts."""
        retryable = await self.dlq.get_retryable_alerts()
        
        if not retryable:
            return
        
        logger.info(f"Processing {len(retryable)} retryable alerts")
        
        for failed_alert in retryable:
            try:
                # Fetch product
                product = await self.dlq.db.get_product(failed_alert.product_id)
                
                if not product:
                    logger.warning(f"Product {failed_alert.product_id} not found, marking as resolved")
                    await self.dlq.mark_resolved(failed_alert.id)
                    continue
                
                # Create alert
                alert = StockAlert(
                    product=product,
                    alert_type=failed_alert.alert_type,
                    timestamp=datetime.now()
                )
                
                # Attempt to send
                success = await self.send_callback(alert)
                
                if success:
                    await self.dlq.mark_resolved(failed_alert.id)
                    logger.info(f"Successfully retried alert {failed_alert.id}")
                else:
                    await self.dlq.increment_retry(failed_alert.id)
                    logger.warning(f"Retry failed for alert {failed_alert.id}")
                    
            except Exception as e:
                logger.error(f"Error processing retry for alert {failed_alert.id}: {e}")
                await self.dlq.increment_retry(failed_alert.id)
