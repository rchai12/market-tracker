"""Seed the database with S&P 500 stocks for Energy and Financials sectors."""

import asyncio

from sqlalchemy import select
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


async def seed():
    async with async_session() as session:
        # Create sectors
        energy = await get_or_create_sector(session, "Energy", is_active=True)
        financials = await get_or_create_sector(session, "Financials", is_active=True)

        # Also create inactive sectors for future expansion
        for name in [
            "Technology", "Health Care", "Consumer Discretionary",
            "Communication Services", "Industrials", "Consumer Staples",
            "Utilities", "Real Estate", "Materials",
        ]:
            await get_or_create_sector(session, name, is_active=False)

        await session.flush()

        # Seed stocks
        count = 0
        for ticker, name in ENERGY_STOCKS:
            created = await get_or_create_stock(session, ticker, name, energy.id)
            if created:
                count += 1

        for ticker, name in FINANCIALS_STOCKS:
            created = await get_or_create_stock(session, ticker, name, financials.id)
            if created:
                count += 1

        await session.commit()
        print(f"Seeded {count} new stocks across Energy and Financials sectors")


async def get_or_create_sector(session: AsyncSession, name: str, is_active: bool) -> Sector:
    result = await session.execute(select(Sector).where(Sector.name == name))
    sector = result.scalar_one_or_none()
    if sector is None:
        sector = Sector(name=name, is_active=is_active)
        session.add(sector)
        await session.flush()
    return sector


async def get_or_create_stock(session: AsyncSession, ticker: str, name: str, sector_id: int) -> bool:
    result = await session.execute(select(Stock).where(Stock.ticker == ticker))
    if result.scalar_one_or_none() is None:
        session.add(Stock(ticker=ticker, company_name=name, sector_id=sector_id, is_active=True))
        return True
    return False


if __name__ == "__main__":
    asyncio.run(seed())
