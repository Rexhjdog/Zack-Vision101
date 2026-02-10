import asyncio
from datetime import datetime
from typing import List, Optional
import discord
from config import CHECK_INTERVAL, RETAILERS
from database import Database
from models import Product, StockAlert
from scrapers import (
    EBGamesScraper,
    JBHiFiScraper,
    TargetScraper,
    BigWScraper,
    KmartScraper
)

class StockScheduler:
    """Scheduler for checking stock across all retailers"""
    
    def __init__(self, bot: discord.Client, db: Database):
        self.bot = bot
        self.db = db
        self.running = False
        self.last_check: Optional[datetime] = None
        
        # Initialize scrapers
        self.scrapers = {
            'eb_games': EBGamesScraper(),
            'jb_hifi': JBHiFiScraper(),
            'target': TargetScraper(),
            'big_w': BigWScraper(),
            'kmart': KmartScraper(),
        }
    
    async def start(self):
        """Start the scheduler"""
        self.running = True
        print("🚀 Starting stock monitoring scheduler...")
        
        # Start the monitoring loop
        asyncio.create_task(self._monitoring_loop())
    
    async def stop(self):
        """Stop the scheduler"""
        self.running = False
        print("🛑 Stopping stock monitoring scheduler...")
    
    async def _monitoring_loop(self):
        """Main monitoring loop that runs every CHECK_INTERVAL seconds"""
        while self.running:
            try:
                print(f"\n🔍 Checking stock at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                await self._check_all_retailers()
                self.last_check = datetime.now()
                
                # Wait for next check
                await asyncio.sleep(CHECK_INTERVAL)
            
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _check_all_retailers(self):
        """Check stock for all enabled retailers"""
        all_new_products = []
        
        for retailer_key, config in RETAILERS.items():
            if not config.get('enabled', True):
                continue
            
            try:
                print(f"  Checking {config['name']}...")
                scraper = self.scrapers.get(retailer_key)
                
                if not scraper:
                    continue
                
                async with scraper:
                    # Search for Pokemon booster boxes ONLY
                    pokemon_products = await scraper.search_products('pokemon booster box')
                    
                    # Search for One Piece booster boxes ONLY
                    onepiece_products = await scraper.search_products('one piece booster box')
                    
                    all_products = pokemon_products + onepiece_products
                    
                    for product in all_products:
                        await self._process_product(product)
                    
                    all_new_products.extend(all_products)
                    print(f"    Found {len(all_products)} products")
            
            except Exception as e:
                print(f"    ❌ Error checking {config['name']}: {e}")
        
        print(f"✅ Completed check. Total products: {len(all_new_products)}")
    
    async def _process_product(self, product: Product):
        """Process a product and check for stock changes"""
        try:
            # Update last checked time
            product.last_checked = datetime.now()
            
            # Get previous state from database
            previous = self.db.get_product(product.id)
            
            if previous:
                # Check for stock status change
                if product.in_stock and not previous.in_stock:
                    # Product came back in stock!
                    print(f"🚨 STOCK ALERT: {product.name} at {product.retailer}")
                    
                    # Update last in stock time
                    product.last_in_stock = datetime.now()
                    
                    # Create alert
                    alert = StockAlert(
                        product=product,
                        alert_type='in_stock',
                        timestamp=datetime.now(),
                        previous_status=previous.in_stock,
                        message=f"Back in stock at {product.retailer}!"
                    )
                    
                    self.db.save_alert(alert)
                    await self._send_alert(alert)
                
                # Check for price change
                elif product.price != previous.price and product.price is not None:
                    print(f"💰 Price change: {product.name} ${previous.price} -> ${product.price}")
                    
                    alert = StockAlert(
                        product=product,
                        alert_type='price_change',
                        timestamp=datetime.now(),
                        previous_price=previous.price
                    )
                    
                    self.db.save_alert(alert)
            else:
                # New product discovered
                print(f"📦 New product: {product.name} at {product.retailer}")
                if product.in_stock:
                    product.last_in_stock = datetime.now()
            
            # Save product to database
            self.db.save_product(product)
            
            # Save stock history
            self.db.save_stock_history(product)
        
        except Exception as e:
            print(f"Error processing product {product.name}: {e}")
    
    async def _send_alert(self, alert: StockAlert):
        """Send Discord alert for stock change"""
        try:
            # Import here to avoid circular import
            from bot import send_stock_alert
            await send_stock_alert(alert.product)
        except Exception as e:
            print(f"Error sending Discord alert: {e}")
    
    async def force_check(self) -> List[Product]:
        """Force an immediate stock check"""
        print("🔄 Forcing immediate stock check...")
        await self._check_all_retailers()
        return self.db.get_all_products()
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            'running': self.running,
            'last_check': self.last_check,
            'check_interval': CHECK_INTERVAL,
            'retailers': len([r for r in RETAILERS.values() if r.get('enabled')]),
        }
