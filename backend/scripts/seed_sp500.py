"""Seed the database with S&P 500 stocks across key sectors and market ETFs."""

import asyncio

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine, Base
from app.models.sector import Sector
from app.models.stock import Stock

# Energy sector stocks (S&P 500)
ENERGY_STOCKS = [
    ("XOM", "Exxon Mobil Corporation"),
    ("CVX", "Chevron Corporation"),
    ("COP", "ConocoPhillips"),
    ("SLB", "Schlumberger Limited"),
    ("EOG", "EOG Resources Inc"),
    ("MPC", "Marathon Petroleum Corporation"),
    ("PSX", "Phillips 66"),
    ("VLO", "Valero Energy Corporation"),
    ("OXY", "Occidental Petroleum Corporation"),
    ("WMB", "Williams Companies Inc"),
    ("HAL", "Halliburton Company"),
    ("DVN", "Devon Energy Corporation"),
    ("FANG", "Diamondback Energy Inc"),
    ("KMI", "Kinder Morgan Inc"),
    ("BKR", "Baker Hughes Company"),
    ("CTRA", "Coterra Energy Inc"),
    ("OKE", "ONEOK Inc"),
    ("TRGP", "Targa Resources Corp"),
]

# Financials sector stocks (S&P 500)
FINANCIALS_STOCKS = [
    ("BRK-B", "Berkshire Hathaway Inc"),
    ("JPM", "JPMorgan Chase & Co"),
    ("V", "Visa Inc"),
    ("MA", "Mastercard Incorporated"),
    ("BAC", "Bank of America Corporation"),
    ("WFC", "Wells Fargo & Company"),
    ("GS", "Goldman Sachs Group Inc"),
    ("MS", "Morgan Stanley"),
    ("SPGI", "S&P Global Inc"),
    ("BLK", "BlackRock Inc"),
    ("AXP", "American Express Company"),
    ("C", "Citigroup Inc"),
    ("SCHW", "Charles Schwab Corporation"),
    ("CB", "Chubb Limited"),
    ("MMC", "Marsh & McLennan Companies"),
    ("PGR", "Progressive Corporation"),
    ("ICE", "Intercontinental Exchange Inc"),
    ("AON", "Aon plc"),
    ("CME", "CME Group Inc"),
    ("MCO", "Moody's Corporation"),
    ("USB", "U.S. Bancorp"),
    ("TFC", "Truist Financial Corporation"),
    ("AIG", "American International Group"),
    ("MET", "MetLife Inc"),
    ("ALL", "Allstate Corporation"),
]

# Technology sector stocks (S&P 500)
TECHNOLOGY_STOCKS = [
    ("AAPL", "Apple Inc"),
    ("MSFT", "Microsoft Corporation"),
    ("NVDA", "NVIDIA Corporation"),
    ("AVGO", "Broadcom Inc"),
    ("ORCL", "Oracle Corporation"),
    ("CRM", "Salesforce Inc"),
    ("AMD", "Advanced Micro Devices Inc"),
    ("ADBE", "Adobe Inc"),
    ("CSCO", "Cisco Systems Inc"),
    ("ACN", "Accenture plc"),
    ("INTC", "Intel Corporation"),
    ("IBM", "International Business Machines"),
    ("INTU", "Intuit Inc"),
    ("TXN", "Texas Instruments Inc"),
    ("QCOM", "Qualcomm Inc"),
    ("NOW", "ServiceNow Inc"),
    ("AMAT", "Applied Materials Inc"),
    ("MU", "Micron Technology Inc"),
    ("PANW", "Palo Alto Networks Inc"),
    ("PLTR", "Palantir Technologies Inc"),
]

# Communication Services stocks (S&P 500)
COMMUNICATION_STOCKS = [
    ("GOOGL", "Alphabet Inc Class A"),
    ("META", "Meta Platforms Inc"),
    ("NFLX", "Netflix Inc"),
    ("DIS", "Walt Disney Company"),
    ("CMCSA", "Comcast Corporation"),
    ("TMUS", "T-Mobile US Inc"),
    ("VZ", "Verizon Communications Inc"),
    ("T", "AT&T Inc"),
]

# Consumer Discretionary stocks (S&P 500)
CONSUMER_DISC_STOCKS = [
    ("AMZN", "Amazon.com Inc"),
    ("TSLA", "Tesla Inc"),
    ("HD", "Home Depot Inc"),
    ("MCD", "McDonald's Corporation"),
    ("NKE", "Nike Inc"),
    ("LOW", "Lowe's Companies Inc"),
    ("SBUX", "Starbucks Corporation"),
    ("TJX", "TJX Companies Inc"),
]

# Market ETFs / Indices
MARKET_ETFS = [
    ("SPY", "SPDR S&P 500 ETF Trust"),
    ("QQQ", "Invesco QQQ Trust"),
    ("DIA", "SPDR Dow Jones Industrial Average ETF"),
    ("IWM", "iShares Russell 2000 ETF"),
    ("VTI", "Vanguard Total Stock Market ETF"),
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

        for sector_name, stocks in SECTOR_STOCKS.items():
            sector = await get_or_create_sector(session, sector_name, is_active=True)
            await session.flush()

            for ticker, name in stocks:
                created = await get_or_create_stock(session, ticker, name, sector.id)
                if created:
                    count += 1

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
        print(f"Seeded {count} new stocks across {len(SECTOR_STOCKS)} sectors")


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


async def get_or_create_stock(session: AsyncSession, ticker: str, name: str, sector_id: int) -> bool:
    result = await session.execute(select(Stock).where(Stock.ticker == ticker))
    if result.scalar_one_or_none() is None:
        session.add(Stock(ticker=ticker, company_name=name, sector_id=sector_id, is_active=True))
        return True
    return False


if __name__ == "__main__":
    asyncio.run(seed())
