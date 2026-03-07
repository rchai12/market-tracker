"""Seed the database with S&P 500 stocks across key sectors and market ETFs."""

import asyncio

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine, Base
from app.models.sector import Sector
from app.models.stock import Stock

# Energy sector stocks (S&P 500)
ENERGY_STOCKS = [
    ("XOM", "Exxon Mobil Corporation", "Oil & Gas Integrated"),
    ("CVX", "Chevron Corporation", "Oil & Gas Integrated"),
    ("COP", "ConocoPhillips", "Oil & Gas Integrated"),
    ("OXY", "Occidental Petroleum Corporation", "Oil & Gas Integrated"),
    ("EOG", "EOG Resources Inc", "Oil & Gas E&P"),
    ("DVN", "Devon Energy Corporation", "Oil & Gas E&P"),
    ("FANG", "Diamondback Energy Inc", "Oil & Gas E&P"),
    ("CTRA", "Coterra Energy Inc", "Oil & Gas E&P"),
    ("SLB", "Schlumberger Limited", "Oil & Gas Equipment"),
    ("HAL", "Halliburton Company", "Oil & Gas Equipment"),
    ("BKR", "Baker Hughes Company", "Oil & Gas Equipment"),
    ("MPC", "Marathon Petroleum Corporation", "Oil & Gas Refining"),
    ("PSX", "Phillips 66", "Oil & Gas Refining"),
    ("VLO", "Valero Energy Corporation", "Oil & Gas Refining"),
    ("WMB", "Williams Companies Inc", "Oil & Gas Midstream"),
    ("KMI", "Kinder Morgan Inc", "Oil & Gas Midstream"),
    ("OKE", "ONEOK Inc", "Oil & Gas Midstream"),
    ("TRGP", "Targa Resources Corp", "Oil & Gas Midstream"),
]

# Financials sector stocks (S&P 500)
FINANCIALS_STOCKS = [
    ("BRK-B", "Berkshire Hathaway Inc", "Diversified Financial"),
    ("JPM", "JPMorgan Chase & Co", "Banks"),
    ("BAC", "Bank of America Corporation", "Banks"),
    ("WFC", "Wells Fargo & Company", "Banks"),
    ("GS", "Goldman Sachs Group Inc", "Banks"),
    ("MS", "Morgan Stanley", "Banks"),
    ("C", "Citigroup Inc", "Banks"),
    ("USB", "U.S. Bancorp", "Banks"),
    ("TFC", "Truist Financial Corporation", "Banks"),
    ("V", "Visa Inc", "Payments"),
    ("MA", "Mastercard Incorporated", "Payments"),
    ("AXP", "American Express Company", "Payments"),
    ("SPGI", "S&P Global Inc", "Capital Markets"),
    ("BLK", "BlackRock Inc", "Capital Markets"),
    ("SCHW", "Charles Schwab Corporation", "Capital Markets"),
    ("ICE", "Intercontinental Exchange Inc", "Capital Markets"),
    ("CME", "CME Group Inc", "Capital Markets"),
    ("MCO", "Moody's Corporation", "Capital Markets"),
    ("AON", "Aon plc", "Capital Markets"),
    ("MMC", "Marsh & McLennan Companies", "Capital Markets"),
    ("CB", "Chubb Limited", "Insurance"),
    ("PGR", "Progressive Corporation", "Insurance"),
    ("AIG", "American International Group", "Insurance"),
    ("MET", "MetLife Inc", "Insurance"),
    ("ALL", "Allstate Corporation", "Insurance"),
]

# Technology sector stocks (S&P 500)
TECHNOLOGY_STOCKS = [
    ("AAPL", "Apple Inc", "Consumer Electronics"),
    ("MSFT", "Microsoft Corporation", "Software"),
    ("NVDA", "NVIDIA Corporation", "Semiconductors"),
    ("AVGO", "Broadcom Inc", "Semiconductors"),
    ("AMD", "Advanced Micro Devices Inc", "Semiconductors"),
    ("INTC", "Intel Corporation", "Semiconductors"),
    ("QCOM", "Qualcomm Inc", "Semiconductors"),
    ("TXN", "Texas Instruments Inc", "Semiconductors"),
    ("AMAT", "Applied Materials Inc", "Semiconductors"),
    ("MU", "Micron Technology Inc", "Semiconductors"),
    ("ORCL", "Oracle Corporation", "Software"),
    ("CRM", "Salesforce Inc", "Software"),
    ("ADBE", "Adobe Inc", "Software"),
    ("INTU", "Intuit Inc", "Software"),
    ("NOW", "ServiceNow Inc", "Software"),
    ("PLTR", "Palantir Technologies Inc", "Software"),
    ("CSCO", "Cisco Systems Inc", "IT Services"),
    ("ACN", "Accenture plc", "IT Services"),
    ("IBM", "International Business Machines", "IT Services"),
    ("PANW", "Palo Alto Networks Inc", "Cybersecurity"),
]

# Communication Services stocks (S&P 500)
COMMUNICATION_STOCKS = [
    ("GOOGL", "Alphabet Inc Class A", "Social Media"),
    ("META", "Meta Platforms Inc", "Social Media"),
    ("NFLX", "Netflix Inc", "Streaming & Entertainment"),
    ("DIS", "Walt Disney Company", "Streaming & Entertainment"),
    ("CMCSA", "Comcast Corporation", "Telecom"),
    ("TMUS", "T-Mobile US Inc", "Telecom"),
    ("VZ", "Verizon Communications Inc", "Telecom"),
    ("T", "AT&T Inc", "Telecom"),
]

# Consumer Discretionary stocks (S&P 500)
CONSUMER_DISC_STOCKS = [
    ("AMZN", "Amazon.com Inc", "E-Commerce"),
    ("TSLA", "Tesla Inc", "EV & Auto"),
    ("HD", "Home Depot Inc", "Retail"),
    ("LOW", "Lowe's Companies Inc", "Retail"),
    ("TJX", "TJX Companies Inc", "Retail"),
    ("NKE", "Nike Inc", "Retail"),
    ("MCD", "McDonald's Corporation", "Restaurants"),
    ("SBUX", "Starbucks Corporation", "Restaurants"),
]

# Market ETFs / Indices
MARKET_ETFS = [
    ("SPY", "SPDR S&P 500 ETF Trust", "ETF"),
    ("QQQ", "Invesco QQQ Trust", "ETF"),
    ("DIA", "SPDR Dow Jones Industrial Average ETF", "ETF"),
    ("IWM", "iShares Russell 2000 ETF", "ETF"),
    ("VTI", "Vanguard Total Stock Market ETF", "ETF"),
]

# All sectors and their stocks
SECTOR_STOCKS = {
    "Energy": ENERGY_STOCKS,
    "Financials": FINANCIALS_STOCKS,
    "Technology": TECHNOLOGY_STOCKS,
    "Communication Services": COMMUNICATION_STOCKS,
    "Consumer Discretionary": CONSUMER_DISC_STOCKS,
    "Market ETFs": MARKET_ETFS,
}


async def seed():
    async with async_session() as session:
        count = 0
        updated = 0

        for sector_name, stocks in SECTOR_STOCKS.items():
            sector = await get_or_create_sector(session, sector_name, is_active=True)
            await session.flush()

            for ticker, name, industry in stocks:
                created = await get_or_create_stock(session, ticker, name, sector.id, industry)
                if created:
                    count += 1
                else:
                    # Update industry on existing stocks
                    result = await session.execute(select(Stock).where(Stock.ticker == ticker))
                    stock = result.scalar_one_or_none()
                    if stock and stock.industry != industry:
                        stock.industry = industry
                        updated += 1

        # Create inactive sectors for future expansion
        for name in ["Health Care", "Industrials", "Consumer Staples",
                      "Utilities", "Real Estate", "Materials"]:
            await get_or_create_sector(session, name, is_active=False)

        # Activate any previously-inactive sectors that now have stocks
        for sector_name in SECTOR_STOCKS:
            await session.execute(
                update(Sector).where(Sector.name == sector_name).values(is_active=True)
            )

        await session.commit()
        print(f"Seeded {count} new stocks, updated {updated} industries across {len(SECTOR_STOCKS)} sectors")


async def get_or_create_sector(session: AsyncSession, name: str, is_active: bool) -> Sector:
    result = await session.execute(select(Sector).where(Sector.name == name))
    sector = result.scalar_one_or_none()
    if sector is None:
        sector = Sector(name=name, is_active=is_active)
        session.add(sector)
        await session.flush()
    elif is_active and not sector.is_active:
        sector.is_active = True
    return sector


async def get_or_create_stock(
    session: AsyncSession, ticker: str, name: str, sector_id: int, industry: str | None = None
) -> bool:
    result = await session.execute(select(Stock).where(Stock.ticker == ticker))
    if result.scalar_one_or_none() is None:
        session.add(Stock(
            ticker=ticker, company_name=name, sector_id=sector_id,
            industry=industry, is_active=True,
        ))
        return True
    return False


if __name__ == "__main__":
    asyncio.run(seed())
