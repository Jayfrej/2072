# MT5 to Notion Trading Journal Sync

Automatically sync your MetaTrader 5 closed trades to a Notion database for comprehensive trading journal management.

## Features

- **Automatic Sync**: Continuously sync closed trades from MT5 to Notion
- **Multiple Accounts**: Support for multiple MT5 accounts
- **Duplicate Prevention**: Automatically skips trades that already exist in Notion
- **Comprehensive Data**: Syncs all trade details including profit, commission, swap, timestamps
- **Error Handling**: Robust error handling with detailed logging
- **Flexible Configuration**: Easy setup via environment variables
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Prerequisites

- Python 3.7 or higher
- MetaTrader 5 terminal installed
- Notion account with API access
- Notion database set up for trading data

## Installation

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd mt5-notion-sync
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your Notion integration**
   - Go to [Notion Integrations](https://www.notion.so/my-integrations)
   - Create a new integration and copy the Internal Integration Token
   - Share your trading database with the integration

## Configuration

1. **Copy the environment template**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file with your details**
   ```env
   # Notion Configuration
   NOTION_TOKEN=your_notion_integration_token_here
   DATABASE_ID=your_notion_database_id_or_url_here

   # Sync Configuration
   SYNC_INTERVAL_MINUTES=15
   LOOKBACK_DAYS=30

   # MT5 Accounts
   MT5_ACCOUNT_COUNT=1

   # Account 1 (Main)
   ACCOUNT_1_NAME=Mix
   ACCOUNT_1_LOGIN=your_mt5_login
   ACCOUNT_1_PASSWORD=your_mt5_password
   ACCOUNT_1_SERVER=your_mt5_server
   ACCOUNT_1_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

   # Add more accounts as needed
   # ACCOUNT_2_NAME=FTMO1
   # ACCOUNT_2_LOGIN=another_login
   # etc...
   ```

### Configuration Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `NOTION_TOKEN` | Your Notion integration token | `secret_xyz...` |
| `DATABASE_ID` | Notion database ID or full URL | Can be URL or formatted ID |
| `SYNC_INTERVAL_MINUTES` | How often to sync (minutes) | `15` |
| `LOOKBACK_DAYS` | How many days back to check | `30` |
| `MT5_ACCOUNT_COUNT` | Number of MT5 accounts | `1` |
| `ACCOUNT_X_NAME` | Account display name | `Mix`, `FTMO1` |
| `ACCOUNT_X_LOGIN` | MT5 account number | `12345678` |
| `ACCOUNT_X_PASSWORD` | MT5 account password | `your_password` |
| `ACCOUNT_X_SERVER` | MT5 server name | `MetaQuotes-Demo` |
| `ACCOUNT_X_PATH` | Path to MT5 terminal | `C:\Program Files\...` |

## Notion Database Setup

Your Notion database should have these properties (the sync will work with whatever properties exist):

### Required Properties
- **Name** (Title) - Trade identifier
- **Ticket ID** (Number) - Unique MT5 ticket number

### Recommended Properties
- **Overall** (Select) - Account name
- **Pair** (Select) - Currency pair
- **Type** (Select) - Buy/Sell
- **Open** (Date) - Open time
- **Close** (Date) - Close time
- **Volume** (Number) - Trade size
- **Open Price** (Number) - Entry price
- **Close Price** (Number) - Exit price
- **Profit** (Number) - Raw profit
- **Commission** (Number) - Broker commission
- **SWAP** (Number) - Overnight fees
- **Net Profit** (Formula) - `prop("Profit") + prop("Commission") + prop("SWAP")`
- **Risk** (Number) - Risk percentage
- **TP** (Number) - Take profit level
- **SL** (Number) - Stop loss level
- **Position ID** (Number) - MT5 position ID
- **Order ID** (Number) - MT5 order ID
- **Magic Number** (Number) - EA magic number
- **Comment** (Text) - Trade comment
- **Close Reason** (Text) - Why trade closed

## Usage

### Windows (Easy Method)
Double-click `run_sync.bat` - this will automatically:
- Check Python installation
- Install requirements if needed
- Verify configuration
- Start the sync application

### Manual Method
```bash
python notion_sync.py
```

### Running Options
When you start the application, you'll be prompted to choose:
1. **Run once** - Sync all trades and exit
2. **Run continuously** - Keep syncing at specified intervals

## How It Works

1. **Connects to Notion** - Validates your token and database access
2. **Connects to MT5** - Logs into your configured MT5 accounts
3. **Fetches Trades** - Gets closed trades from the specified lookback period
4. **Checks Duplicates** - Skips trades already in your Notion database
5. **Syncs Data** - Creates new Notion pages for new trades
6. **Logs Everything** - Detailed logs saved to `mt5_notion_sync.log`

## Logging

All sync activities are logged to `mt5_notion_sync.log` including:
- Connection status
- Trades found and processed
- Errors and warnings
- Success confirmations

## Troubleshooting

### Common Issues

**"Database not found" Error**
- Check your `DATABASE_ID` is correct
- Ensure your Notion integration has access to the database
- Try using the full Notion URL instead of just the ID

**"MT5 connection failed"**
- Verify MT5 terminal is installed at the specified path
- Check login credentials are correct
- Ensure MT5 terminal can connect manually first

**"Ticket ID is expected to be title" Error**
- Your Notion database has "Ticket ID" as a Title property
- Either rename it or add a separate "Name" Title property

**Missing Trades**
- Check the `LOOKBACK_DAYS` setting
- Verify trades are actually closed in MT5
- Check the log file for any errors

### Getting Help

1. Check the log file `mt5_notion_sync.log` for detailed error messages
2. Verify all configuration parameters are correct
3. Test Notion connection manually through their API
4. Ensure MT5 terminal can connect and show trade history

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- Your Notion token provides access to your workspace
- MT5 passwords are stored in plain text in the config file
- Consider using environment variables in production environments

## Limitations

- Only syncs closed trades (open positions are not included)
- Requires MT5 terminal to be accessible on the system
- Some MT5 brokers may have API limitations
- Notion API has rate limits (handled automatically)

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the application.

## License

This project is provided as-is for personal use. Please respect broker terms of service and trading regulations in your jurisdiction.
