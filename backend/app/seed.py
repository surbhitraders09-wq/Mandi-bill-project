"""
Seed default settings and demo credentials on first boot.

Credentials are loaded from environment variables (prefix `MANDI_`) so the
repo can be published on GitHub without leaking real passwords. If the env
vars are not set, safe placeholder values are used — set them in a local
`.env` file (see `.env.example`) before first boot.
"""

import os
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.security import encrypt_value, hash_password
from app.database import async_session_factory
from app.models.bill import Bill
from app.models.commodity import Commodity
from app.models.farmer import Farmer
from app.models.settings import Setting
from app.models.trader import Trader
from app.models.user import Role, User
from app.models.village import Village

PLACEHOLDER_USERNAME = "YOUR_TRADER_ID"
PLACEHOLDER_PASSWORD = "YOUR_TRADER_PASSWORD"
PLACEHOLDER_PIN = "0000"


def _env(key: str, default: str) -> str:
    """Read a MANDI_ prefixed env var, falling back to a safe default."""
    return os.environ.get(f"MANDI_{key}", default)


DEFAULT_SETTINGS = {
    "e_mandi_username": _env("E_MANDI_USERNAME", PLACEHOLDER_USERNAME),
    "e_mandi_password": _env("E_MANDI_PASSWORD", PLACEHOLDER_PASSWORD),
    "e_mandi_pin": _env("E_MANDI_PIN", PLACEHOLDER_PIN),
    "e_mandi_url": _env("E_MANDI_URL", "https://eanugya.mp.gov.in/Trader.aspx"),
    "hammali_rate": _env("HAMMALI_RATE", "12.05"),
    "cash_threshold": _env("CASH_THRESHOLD", "200000"),
    "automation_timeout": _env("AUTOMATION_TIMEOUT", "60"),
    "auto_close_browser": _env("AUTO_CLOSE_BROWSER", "true"),
    "ignore_https_errors": _env("IGNORE_HTTPS_ERRORS", "true"),
}

ENCRYPTED_KEYS = {"e_mandi_password", "e_mandi_pin"}

# Demo admin user password — override via MANDI_ADMIN_PASSWORD in production.
ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "admin123")


async def seed_defaults() -> None:
    async with async_session_factory() as session:
        existing = (await session.execute(select(Setting))).scalars().all()
        existing_keys = {s.key for s in existing}

        for key, value in DEFAULT_SETTINGS.items():
            if key in existing_keys:
                continue
            stored = encrypt_value(value) if key in ENCRYPTED_KEYS else value
            session.add(Setting(key=key, value=stored))

        await _seed_roles_and_admin(session)
        await _seed_master_data(session)
        await _seed_demo_bills(session)
        await session.commit()


async def _seed_master_data(session) -> None:
    villages = [
        {"name": "Rewa", "block": "Rewa", "district": "Rewa"},
        {"name": "Semariya", "block": "Semariya", "district": "Rewa"},
        {"name": "Mauganj", "block": "Mauganj", "district": "Rewa"},
        {"name": "Teonthar", "block": "Teonthar", "district": "Rewa"},
        {"name": "Sirmour", "block": "Sirmour", "district": "Rewa"},
    ]
    existing_villages = {v.name for v in (await session.execute(select(Village))).scalars().all()}
    for v in villages:
        if v["name"] not in existing_villages:
            session.add(Village(**v))

    commodities = [
        {"name": "Soybean", "code": "SOY", "unit": "quintal"},
        {"name": "Wheat", "code": "WHT", "unit": "quintal"},
        {"name": "Gram", "code": "GRM", "unit": "quintal"},
        {"name": "Paddy", "code": "PDY", "unit": "quintal"},
        {"name": "Mustard", "code": "MST", "unit": "quintal"},
        {"name": "Lentil", "code": "LNT", "unit": "quintal"},
    ]
    existing_commodities = {c.name for c in (await session.execute(select(Commodity))).scalars().all()}
    for c in commodities:
        if c["name"] not in existing_commodities:
            session.add(Commodity(**c))

    village = (
        await session.execute(select(Village).where(Village.name == "Rewa"))
    ).scalar_one_or_none()

    farmers = [
        {
            "name": "Ram Singh Patel",
            "aadhaar": "123456789012",
            "mobile": "9876543210",
            "village_id": village.id if village else None,
            "land_area": 3.5,
            "bank_name": "State Bank of India",
            "account_number": "30214567890",
            "ifsc_code": "SBIN0000111",
        },
        {
            "name": "Suresh Kumar Verma",
            "aadhaar": "234567890123",
            "mobile": "9765432109",
            "village_id": village.id if village else None,
            "land_area": 2.0,
            "bank_name": "Punjab National Bank",
            "account_number": "11223344556",
            "ifsc_code": "PUNB0000234",
        },
        {
            "name": "Mohan Lal Yadav",
            "aadhaar": "345678901234",
            "mobile": "9654321098",
            "village_id": village.id if village else None,
            "land_area": 4.2,
            "bank_name": "Bank of India",
            "account_number": "99887766554",
            "ifsc_code": "BKID0009001",
        },
    ]
    existing_farmers = {f.aadhaar for f in (await session.execute(select(Farmer))).scalars().all()}
    for f in farmers:
        if f["aadhaar"] not in existing_farmers:
            session.add(Farmer(**f))

    traders = [
        {
            "name": "Sharma Traders",
            "gstin": "23ABCDE1234F1Z5",
            "pan": "ABCDE1234F",
            "license_no": "RWA-MKT-001",
            "mobile": "9876501234",
            "commission_rate": 1.0,
        },
        {
            "name": "Agro Corporation",
            "gstin": "23FGHIJ5678K1L2",
            "pan": "FGHIJ5678K",
            "license_no": "RWA-MKT-002",
            "mobile": "9876512345",
            "commission_rate": 1.5,
        },
        {
            "name": "Ganga Mandi House",
            "gstin": "23MNOPQ9012R3S4",
            "pan": "MNOPQ9012R",
            "license_no": "RWA-MKT-003",
            "mobile": "9876523456",
            "commission_rate": 0.75,
        },
    ]
    existing_traders = {t.gstin for t in (await session.execute(select(Trader))).scalars().all()}
    for t in traders:
        if t["gstin"] not in existing_traders:
            session.add(Trader(**t))


async def _seed_demo_bills(session) -> None:
    commodities = {
        c.name: c for c in (await session.execute(select(Commodity))).scalars().all()
    }
    traders = {
        t.name: t for t in (await session.execute(select(Trader))).scalars().all()
    }
    existing_numbers = set(
        (await session.execute(select(Bill.bill_number))).scalars().all()
    )

    trader_bills = [
        ("SOY-0001", "Sharma Traders", "Soybean", 1200, 4500, "MP09-1234"),
        ("SOY-0002", "Agro Corporation", "Soybean", 1800, 4450, "MP09-2234"),
        ("WHT-0001", "Sharma Traders", "Wheat", 2500, 2300, "MP09-3234"),
        ("WHT-0002", "Ganga Mandi House", "Wheat", 1500, 2280, "MP09-4234"),
        ("GRM-0001", "Agro Corporation", "Gram", 900, 5600, "MP09-5234"),
        ("PDY-0001", "Sharma Traders", "Paddy", 3000, 2200, "MP09-6234"),
        ("MST-0001", "Ganga Mandi House", "Mustard", 700, 6100, "MP09-7234"),
        ("LNT-0001", "Agro Corporation", "Lentil", 800, 5800, "MP09-8234"),
    ]
    government_bills = [
        ("SOY-0003", "Soybean", 5000, 4650, "MP09-1001"),
        ("WHT-0003", "Wheat", 8000, 2420, "MP09-1002"),
        ("GRM-0002", "Gram", 2000, 5850, "MP09-1003"),
        ("PDY-0002", "Paddy", 10000, 2250, "MP09-1004"),
    ]

    specs: list[dict] = []
    for bill_number, trader_name, commodity, weight, rate, vehicle in trader_bills:
        trader = traders.get(trader_name)
        commodity_obj = commodities.get(commodity)
        specs.append(
            {
                "trader_name": trader_name,
                "bill_number": bill_number,
                "commodity": commodity,
                "weight": weight,
                "rate": rate,
                "vehicle_number": vehicle,
                "segment": "trader",
                "commodity_id": commodity_obj.id if commodity_obj else None,
                "farmer_id": trader.id if trader else None,
            }
        )
    for bill_number, commodity, weight, rate, vehicle in government_bills:
        commodity_obj = commodities.get(commodity)
        specs.append(
            {
                "trader_name": "MP State Civil Supplies",
                "bill_number": bill_number,
                "commodity": commodity,
                "weight": weight,
                "rate": rate,
                "vehicle_number": vehicle,
                "segment": "government",
                "commodity_id": commodity_obj.id if commodity_obj else None,
                "farmer_id": None,
            }
        )

    base = datetime.utcnow()
    day_offsets = [1, 3, 5, 8, 11, 13, 16, 19, 22, 25, 27, 29]
    for i, spec in enumerate(specs):
        if spec["bill_number"] in existing_numbers:
            continue
        weight = spec["weight"]
        rate = spec["rate"]
        gross_amount = round((weight * rate) / 100.0, 2)
        hammali_amount = round((weight / 100.0) * 12.05, 2)
        total_amount = round(gross_amount + hammali_amount, 2)
        bill_date = (base - timedelta(days=day_offsets[i])).replace(
            hour=9, minute=30, second=0, microsecond=0
        )
        session.add(
            Bill(
                trader_name=spec["trader_name"],
                bill_number=spec["bill_number"],
                commodity=spec["commodity"],
                date=bill_date,
                created_at=bill_date,
                vehicle_number=spec["vehicle_number"],
                weight=weight,
                rate=rate,
                gross_amount=gross_amount,
                hammali_rate=12.05,
                hammali_amount=hammali_amount,
                total_amount=total_amount,
                segment=spec["segment"],
                commodity_id=spec["commodity_id"],
                farmer_id=spec["farmer_id"],
            )
        )


async def _seed_roles_and_admin(session) -> None:
    existing_roles = {r.name for r in (await session.execute(select(Role))).scalars().all()}
    role_map: dict[str, int] = {}
    for name, desc in [
        ("administrator", "Full access"),
        ("operator", "Operations"),
        ("accountant", "Finance"),
        ("inspector", "View-only audit"),
    ]:
        role = (await session.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
        if role is None:
            role = Role(name=name, description=desc)
            session.add(role)
            await session.flush()
        role_map[name] = role.id

    admin = (
        await session.execute(select(User).where(User.username == "admin"))
    ).scalar_one_or_none()
    if admin is None:
        session.add(
            User(
                username="admin",
                full_name="System Administrator",
                password_hash=hash_password(ADMIN_PASSWORD),
                role_id=role_map["administrator"],
            )
        )
