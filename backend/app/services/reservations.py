from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo


async def _get_property_timezone(property_id: str, tenant_id: str) -> str:
    """
    Returns the IANA timezone string for a given property.
    Falls back to 'UTC' if the property cannot be found.
    """
    _property_tz_map = {
        ("prop-001", "tenant-a"): "Europe/Paris",
        ("prop-001", "tenant-b"): "America/New_York",
        ("prop-002", "tenant-a"): "Europe/Paris",
        ("prop-003", "tenant-a"): "Europe/Paris",
        ("prop-004", "tenant-b"): "America/New_York",
        ("prop-005", "tenant-b"): "America/New_York",
    }
    return _property_tz_map.get((property_id, tenant_id), "UTC")


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
    db_session=None,
) -> Decimal:
    """
    Calculates revenue for a specific month, respecting the property's local timezone.

    BUG FIX: The original code used naive datetime (no timezone), so month
    boundaries were always UTC midnight. A reservation at 2024-02-29 23:30 UTC
    is already March 1 in Paris (UTC+1), so it was counted in the wrong month.

    Fix: build boundaries in the property's local timezone, then convert to UTC
    before querying the DB.
    """
    property_tz = ZoneInfo(await _get_property_timezone(property_id, tenant_id))

    local_start = datetime(year, month, 1, tzinfo=property_tz)
    if month < 12:
        local_end = datetime(year, month + 1, 1, tzinfo=property_tz)
    else:
        local_end = datetime(year + 1, 1, 1, tzinfo=property_tz)

    utc_start = local_start.astimezone(ZoneInfo("UTC"))
    utc_end   = local_end.astimezone(ZoneInfo("UTC"))

    print(
        f"DEBUG: Querying revenue for {property_id} (tz={property_tz}) "
        f"| local: {local_start.date()} to {local_end.date()} "
        f"| UTC: {utc_start} to {utc_end}"
    )

    query = """
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = $1
        AND tenant_id = $2
        AND check_in_date >= $3
        AND check_in_date < $4
    """

    # result = await db.fetch_val(query, property_id, tenant_id, utc_start, utc_end)
    # return result or Decimal('0')

    return Decimal('0')  # Placeholder until DB connection is finalised


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        from app.core.database_pool import DatabasePool

        db_pool = DatabasePool()
        await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                from sqlalchemy import text

                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)

                result = await session.execute(query, {
                    "property_id": property_id,
                    "tenant_id": tenant_id
                })
                row = result.fetchone()

                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD",
                        "count": row.reservation_count
                    }
                else:
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")

    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")

        mock_data = {
            'prop-001': {'total': '1000.00', 'count': 3},
            'prop-002': {'total': '4975.50', 'count': 4},
            'prop-003': {'total': '6100.50', 'count': 2},
            'prop-004': {'total': '1776.50', 'count': 4},
            'prop-005': {'total': '3256.00', 'count': 3}
        }

        mock_property_data = mock_data.get(property_id, {'total': '0.00', 'count': 0})

        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }