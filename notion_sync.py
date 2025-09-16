#!/usr/bin/env python3
"""
MT5 to Notion Trading Journal Sync
Automatically syncs closed trades from MetaTrader 5 to Notion database
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re

# Fix encoding issues on Windows
if sys.platform.startswith('win'):
    import codecs
    # Set console output to UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Third-party imports
try:
    from dotenv import load_dotenv
    import MetaTrader5 as mt5
    import pandas as pd
    from notion_client import Client
    from notion_client.errors import APIResponseError, RequestTimeoutError
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install with: pip install -r requirements.txt")
    sys.exit(1)

# Custom formatter to handle Unicode characters safely
class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Replace problematic Unicode characters with safe alternatives
        formatted = super().format(record)
        # Replace checkmark with simple text
        formatted = formatted.replace('Ã¢Å""', '[SUCCESS]')
        formatted = formatted.replace('Ã¢Å"â€"', '[ERROR]')
        return formatted

# Configure logging with safe encoding
def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = SafeFormatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler with explicit UTF-8 encoding
    try:
        file_handler = logging.FileHandler('mt5_notion_sync.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

class NotionSyncConfig:
    """Configuration handler for the sync application"""
    
    def __init__(self):
        load_dotenv()
        self.notion_token = os.getenv("NOTION_TOKEN")
        raw_database_id = os.getenv("DATABASE_ID") or os.getenv("NOTION_DATABASE_URL")
        self.database_id = self._process_database_id(raw_database_id)
        self.accounts = self._load_mt5_accounts()
        self.sync_interval = int(os.getenv("SYNC_INTERVAL_MINUTES", "15"))
        self.lookback_days = int(os.getenv("LOOKBACK_DAYS", "30"))
        
    def _process_database_id(self, raw_input: str) -> str:
        """Process and validate database ID or URL"""
        if not raw_input:
            logger.error("No database ID or URL provided")
            return ""
        
        logger.info(f"Processing database input: {raw_input[:50]}...")
        
        # If it's already a clean database ID (32 hex chars with hyphens)
        if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', raw_input, re.IGNORECASE):
            logger.info("Input is already a formatted database ID")
            return raw_input
            
        # If it's a raw database ID (32 hex chars without hyphens)
        if re.match(r'^[a-f0-9]{32}$', raw_input, re.IGNORECASE):
            logger.info("Converting raw database ID to formatted version")
            return f"{raw_input[:8]}-{raw_input[8:12]}-{raw_input[12:16]}-{raw_input[16:20]}-{raw_input[20:]}"
        
        # If it contains notion.so, extract database ID from URL
        if "notion.so" in raw_input:
            logger.info("Extracting database ID from Notion URL")
            
            # Remove all hyphens first to find continuous hex string
            clean_url = raw_input.replace('-', '').replace('_', '')
            
            # Look for 32 consecutive hex characters
            match = re.search(r'([a-f0-9]{32})', clean_url, re.IGNORECASE)
            if match:
                db_id = match.group(1).lower()
                formatted_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"
                logger.info(f"Extracted and formatted database ID: {formatted_id}")
                return formatted_id
            else:
                logger.error("Could not extract database ID from URL")
                return ""
        
        # If it doesn't match any pattern, try to use as-is
        logger.warning(f"Unknown database ID format, using as-is: {raw_input}")
        return raw_input
    
    def _load_mt5_accounts(self) -> List[Dict]:
        """Load MT5 account configurations"""
        accounts = []
        account_count = int(os.getenv("MT5_ACCOUNT_COUNT", "0"))
        
        for i in range(1, account_count + 1):
            account = {
                'name': os.getenv(f"ACCOUNT_{i}_NAME"),
                'login': os.getenv(f"ACCOUNT_{i}_LOGIN"),
                'password': os.getenv(f"ACCOUNT_{i}_PASSWORD"),
                'server': os.getenv(f"ACCOUNT_{i}_SERVER"),
                'path': os.getenv(f"ACCOUNT_{i}_PATH")
            }
            
            # Skip incomplete accounts
            if not all(account.values()):
                logger.warning(f"Skipping incomplete account {i}: {account['name']}")
                continue
                
            try:
                account['login'] = int(account['login'])
                accounts.append(account)
            except ValueError:
                logger.error(f"Invalid login number for account {i}: {account['login']}")
                
        return accounts
    
    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        if not self.notion_token:
            logger.error("NOTION_TOKEN is missing")
            return False
            
        if not self.database_id:
            logger.error("DATABASE_ID or NOTION_DATABASE_URL is missing")
            return False
            
        if not self.accounts:
            logger.error("No valid MT5 accounts configured")
            return False
            
        return True

class NotionClient:
    """Enhanced Notion client with error handling"""
    
    def __init__(self, token: str):
        self.client = Client(auth=token)
        self.database_properties = {}
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test Notion connection and get user info"""
        try:
            user = self.client.users.me()
            return True, user.get('name', 'Unknown User')
        except Exception as e:
            return False, str(e)
    
    def get_database_info(self, database_id: str) -> Tuple[bool, Dict]:
        """Get database information and cache properties"""
        try:
            logger.info(f"Attempting to retrieve database: {database_id}")
            database = self.client.databases.retrieve(database_id=database_id)
            self.database_properties = database['properties']
            
            title = "Unnamed Database"
            if database.get('title') and database['title']:
                title = database['title'][0]['plain_text']
                
            return True, {
                'title': title,
                'properties': list(self.database_properties.keys())
            }
        except APIResponseError as e:
            if e.status == 404:
                return False, "Database not found. Check ID and integration permissions."
            elif e.status == 401:
                return False, "Unauthorized. Check your Notion token."
            return False, f"API Error: {e}"
        except Exception as e:
            return False, str(e)
    
    def check_existing_trade(self, database_id: str, ticket_id: int) -> bool:
        """Check if trade already exists in database"""
        try:
            results = self.client.databases.query(
                database_id=database_id,
                filter={
                    "property": "Ticket ID",
                    "number": {"equals": ticket_id}
                }
            )
            return len(results['results']) > 0
        except Exception as e:
            logger.warning(f"Could not check existing trade {ticket_id}: {e}")
            return False
    
    def create_trade_page(self, database_id: str, trade_data: Dict) -> Tuple[bool, str]:
        """Create a new trade page in Notion"""
        try:
            properties = self._build_properties(trade_data)
            
            new_page = {
                "parent": {"database_id": database_id},
                "properties": properties
            }
            
            self.client.pages.create(**new_page)
            return True, f"Trade {trade_data['ticket']} added successfully"
            
        except APIResponseError as e:
            return False, f"API Error creating trade: {e}"
        except Exception as e:
            return False, f"Error creating trade: {e}"
    
    def _build_properties(self, trade_data: Dict) -> Dict:
        """Build Notion properties from trade data"""
        properties = {}
        
        # Property mappings based on your table
        mappings = {
            "Name": ("title", str(trade_data.get('ticket', ''))),
            "Overall": ("select", trade_data.get('account_name', 'Unknown')),
            "Pair": ("select", str(trade_data.get('symbol', 'Unknown'))),
            "Type": ("select", trade_data.get('type', 'Unknown')),
            "Open": ("date", trade_data.get('open_time')),
            "Close": ("date", trade_data.get('close_time')),
            "Volume": ("number", float(trade_data.get('volume', 0))),
            "Open Price": ("number", float(trade_data.get('open_price', 0))),
            "Close Price": ("number", float(trade_data.get('close_price', 0))),
            "Profit": ("number", float(trade_data.get('profit', 0))),
            "Commission": ("number", float(trade_data.get('commission', 0))),
            "SWAP": ("number", float(trade_data.get('swap', 0))),
            "Net Profit": ("formula", None),  # This will be calculated by Notion formula
            "Risk": ("number", float(trade_data.get('risk_percent', 0))),
            "TP": ("number", float(trade_data.get('tp_price', 0))),
            "SL": ("number", float(trade_data.get('sl_price', 0))),
            "S/L Price": ("number", float(trade_data.get('sl_price', 0))),
            "T/P Price": ("number", float(trade_data.get('tp_price', 0))),
            "Ticket ID": ("number", int(trade_data.get('ticket', 0))),
            "Position ID": ("number", int(trade_data.get('position_id', 0))),
            "Order ID": ("number", int(trade_data.get('order_id', 0))),
            "Magic Number": ("number", int(trade_data.get('magic', 0))),
            "Comment": ("text", str(trade_data.get('comment', ''))),
            "Close Reason": ("text", str(trade_data.get('close_reason', '')))
        }
        
        for prop_name, (prop_type, value) in mappings.items():
            # Skip if property doesn't exist in database or if it's a formula
            if prop_name not in self.database_properties or prop_type == "formula":
                continue
                
            try:
                if prop_type == "title":
                    properties[prop_name] = {
                        "title": [{"text": {"content": str(value)}}]
                    }
                elif prop_type == "select":
                    properties[prop_name] = {
                        "select": {"name": str(value)}
                    }
                elif prop_type == "number" and value is not None:
                    properties[prop_name] = {
                        "number": float(value) if value != 0 else None
                    }
                elif prop_type == "date" and value:
                    properties[prop_name] = {
                        "date": {"start": value}
                    }
                elif prop_type == "text" and value:
                    properties[prop_name] = {
                        "rich_text": [{"text": {"content": str(value)}}]
                    }
            except Exception as e:
                logger.warning(f"Could not set property {prop_name}: {e}")
                
        return properties

class MT5Manager:
    """MT5 connection and data management"""
    
    def __init__(self, account: Dict):
        self.account = account
        self.connected = False
    
    def connect(self) -> Tuple[bool, str]:
        """Connect to MT5 account"""
        try:
            success = mt5.initialize(
                path=self.account['path'],
                login=self.account['login'],
                password=self.account['password'],
                server=self.account['server']
            )
            
            if not success:
                error = mt5.last_error()
                return False, f"MT5 connection failed: {error}"
            
            # Verify connection
            account_info = mt5.account_info()
            if account_info is None:
                return False, "Connected but cannot get account info"
                
            self.connected = True
            return True, f"Connected to account {account_info.login}"
            
        except Exception as e:
            return False, f"Connection error: {e}"
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
    
    def get_closed_trades(self, days_back: int = 30) -> List[Dict]:
        """Get closed trades from MT5"""
        if not self.connected:
            return []
        
        try:
            from_date = datetime.now() - timedelta(days=days_back)
            to_date = datetime.now()
            
            # Get deal history
            deals = mt5.history_deals_get(from_date, to_date)
            if not deals:
                logger.info(f"No deals found for account {self.account['name']}")
                return []
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
            
            # Process closed positions
            closed_trades = self._process_closed_positions(df)
            
            logger.info(f"Found {len(closed_trades)} closed trades for {self.account['name']}")
            return closed_trades
            
        except Exception as e:
            logger.error(f"Error getting trades for {self.account['name']}: {e}")
            return []
    
    def _process_closed_positions(self, df: pd.DataFrame) -> List[Dict]:
        """Process deals to identify closed positions"""
        closed_trades = []
        
        # Separate entry and exit deals
        entry_deals = df[df['entry'] == mt5.DEAL_ENTRY_IN].set_index('position_id')
        exit_deals = df[df['entry'] == mt5.DEAL_ENTRY_OUT]
        
        for _, exit_deal in exit_deals.iterrows():
            position_id = exit_deal['position_id']
            
            # Find corresponding entry deal
            if position_id not in entry_deals.index:
                continue
                
            entry_deal = entry_deals.loc[position_id]
            if isinstance(entry_deal, pd.DataFrame):
                entry_deal = entry_deal.iloc[0]
            
            # Determine close reason
            close_reason = "Manual Close"
            if hasattr(exit_deal, 'reason'):
                if exit_deal['reason'] == mt5.DEAL_REASON_SL:
                    close_reason = "Stop Loss"
                elif exit_deal['reason'] == mt5.DEAL_REASON_TP:
                    close_reason = "Take Profit"
            
            # Build trade data
            trade_data = {
                'ticket': int(exit_deal['ticket']),
                'position_id': int(position_id),
                'order_id': int(getattr(exit_deal, 'order', 0)),
                'symbol': str(exit_deal['symbol']),
                'type': 'Buy' if entry_deal['type'] == mt5.DEAL_TYPE_BUY else 'Sell',
                'volume': float(exit_deal['volume']),
                'open_price': float(entry_deal['price']),
                'close_price': float(exit_deal['price']),
                'open_time': pd.to_datetime(entry_deal['time'], unit='s').isoformat(),
                'close_time': pd.to_datetime(exit_deal['time'], unit='s').isoformat(),
                'profit': float(exit_deal['profit']),
                'commission': float(exit_deal['commission']),
                'swap': float(exit_deal['swap']),
                'magic': int(getattr(entry_deal, 'magic', 0)),
                'comment': str(getattr(entry_deal, 'comment', '')),
                'close_reason': close_reason,
                'account_name': self.account['name'],
                # Additional fields that might be useful
                'sl_price': 0.0,  # You may need to get this from position history
                'tp_price': 0.0,  # You may need to get this from position history
                'risk_percent': 0.0,  # Calculate based on your risk management
            }
            
            closed_trades.append(trade_data)
            
        return closed_trades

class MT5NotionSync:
    """Main sync application"""
    
    def __init__(self):
        self.config = NotionSyncConfig()
        self.notion_client = None
        self.running = False
    
    def initialize(self) -> bool:
        """Initialize the sync application"""
        logger.info("Initializing MT5 to Notion Sync")
        
        # Check configuration
        if not self.config.is_valid():
            logger.error("Invalid configuration")
            return False
        
        # Initialize Notion client
        self.notion_client = NotionClient(self.config.notion_token)
        
        # Test Notion connection
        success, message = self.notion_client.test_connection()
        if not success:
            logger.error(f"Notion connection failed: {message}")
            return False
        
        logger.info(f"Connected to Notion as: {message}")
        
        # Test database access
        success, db_info = self.notion_client.get_database_info(self.config.database_id)
        if not success:
            logger.error(f"Database access failed: {db_info}")
            return False
        
        logger.info(f"Connected to database: {db_info['title']}")
        logger.info(f"Database properties: {', '.join(db_info['properties'])}")
        
        return True
    
    def sync_account(self, account: Dict) -> Tuple[int, int]:
        """Sync one MT5 account to Notion"""
        logger.info(f"Syncing account: {account['name']}")
        
        mt5_manager = MT5Manager(account)
        success_count = 0
        error_count = 0
        
        try:
            # Connect to MT5
            success, message = mt5_manager.connect()
            if not success:
                logger.error(f"Cannot connect to {account['name']}: {message}")
                return 0, 1
            
            logger.info(f"MT5 {message}")
            
            # Get closed trades
            trades = mt5_manager.get_closed_trades(self.config.lookback_days)
            
            for trade in trades:
                try:
                    # Check if trade already exists
                    if self.notion_client.check_existing_trade(
                        self.config.database_id, trade['ticket']
                    ):
                        logger.debug(f"Trade {trade['ticket']} already exists, skipping")
                        continue
                    
                    # Create new trade in Notion
                    success, message = self.notion_client.create_trade_page(
                        self.config.database_id, trade
                    )
                    
                    if success:
                        logger.info(f"[SUCCESS] {message}")
                        success_count += 1
                    else:
                        logger.error(f"[ERROR] Failed to add trade {trade['ticket']}: {message}")
                        error_count += 1
                    
                    # Small delay to avoid rate limits
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing trade {trade.get('ticket', 'Unknown')}: {e}")
                    error_count += 1
            
        finally:
            mt5_manager.disconnect()
        
        logger.info(f"Account {account['name']} sync completed: "
                   f"{success_count} added, {error_count} errors")
        return success_count, error_count
    
    def run_sync_cycle(self) -> bool:
        """Run one complete sync cycle for all accounts"""
        logger.info("Starting sync cycle")
        total_success = 0
        total_errors = 0
        
        for account in self.config.accounts:
            try:
                success, errors = self.sync_account(account)
                total_success += success
                total_errors += errors
                
                # Brief pause between accounts
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Unexpected error syncing {account['name']}: {e}")
                total_errors += 1
        
        logger.info(f"Sync cycle completed: {total_success} trades added, "
                   f"{total_errors} errors")
        
        return total_errors == 0
    
    def run_continuous(self):
        """Run continuous sync with specified interval"""
        self.running = True
        logger.info(f"Starting continuous sync (interval: {self.config.sync_interval} minutes)")
        
        try:
            while self.running:
                self.run_sync_cycle()
                
                if self.running:
                    logger.info(f"Waiting {self.config.sync_interval} minutes for next sync...")
                    time.sleep(self.config.sync_interval * 60)
                    
        except KeyboardInterrupt:
            logger.info("Sync stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in continuous sync: {e}")
        finally:
            self.running = False
            logger.info("Sync application terminated")
    
    def stop(self):
        """Stop the sync application"""
        self.running = False

def main():
    """Main entry point"""
    print("=" * 60)
    print("MT5 to Notion Trading Journal Sync")
    print("=" * 60)
    
    # Create and initialize sync app
    sync_app = MT5NotionSync()
    
    if not sync_app.initialize():
        logger.error("Failed to initialize sync application")
        sys.exit(1)
    
    # Show configuration
    logger.info("Configuration:")
    logger.info(f"  - Accounts: {[acc['name'] for acc in sync_app.config.accounts]}")
    logger.info(f"  - Lookback days: {sync_app.config.lookback_days}")
    logger.info(f"  - Sync interval: {sync_app.config.sync_interval} minutes")
    
    try:
        # Ask for run mode
        print("\nSelect run mode:")
        print("1. Run once")
        print("2. Run continuously")
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            sync_app.run_sync_cycle()
        elif choice == "2":
            sync_app.run_continuous()
        else:
            logger.error("Invalid choice")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()