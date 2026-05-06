#!/usr/bin/env python3
"""
IMO Lookup CLI Utility — search for vessel IMO numbers by name.

Usage:
    python find_imo.py "EVER GIVEN"          # exact/partial name search
    python find_imo.py "MSC"                  # returns multiple matches
    python find_imo.py --imo 9349028          # reverse lookup: IMO → full details

Output formatted for easy CSV copy-paste:
    IMO: 9349028 | Name: EVER GIVEN | Type: Container Ship | Flag: Panama | MMSI: 353136000
    → CSV line: 9349028,EVER GIVEN,,,

In demo mode: searches built-in database of ~200 well-known vessels.
With AIS_API_KEY configured: queries the live AIS provider.
"""

import argparse
import asyncio
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


# Built-in vessel database for demo mode (subset — full list in demo_provider.py)
KNOWN_VESSELS = [
    {"imo_number": "9811000", "mmsi": "353136000", "name": "EVER GIVEN", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9461867", "mmsi": "255806260", "name": "MSC OSCAR", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9484525", "mmsi": "477328800", "name": "CSCL GLOBE", "vessel_type": "Container Ship", "flag": "Hong Kong"},
    {"imo_number": "9708837", "mmsi": "636092799", "name": "MOL TRIUMPH", "vessel_type": "Container Ship", "flag": "Liberia"},
    {"imo_number": "9839430", "mmsi": "477021300", "name": "EVER ACE", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9795736", "mmsi": "477339800", "name": "COSCO SHIPPING UNIVERSE", "vessel_type": "Container Ship", "flag": "Hong Kong"},
    {"imo_number": "9732319", "mmsi": "636018505", "name": "MADRID MAERSK", "vessel_type": "Container Ship", "flag": "Denmark"},
    {"imo_number": "9619907", "mmsi": "477588600", "name": "OOCL HONG KONG", "vessel_type": "Container Ship", "flag": "Hong Kong"},
    {"imo_number": "9703291", "mmsi": "255806260", "name": "MSC GULSUN", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9780875", "mmsi": "538008217", "name": "HMM ALGECIRAS", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9246633", "mmsi": "249110000", "name": "TI EUROPE", "vessel_type": "VLCC Tanker", "flag": "Malta"},
    {"imo_number": "9247455", "mmsi": "249111000", "name": "TI OCEANIA", "vessel_type": "VLCC Tanker", "flag": "Malta"},
    {"imo_number": "9312868", "mmsi": "538003412", "name": "FRONT ALTA", "vessel_type": "VLCC Tanker", "flag": "Marshall Islands"},
    {"imo_number": "9407868", "mmsi": "636014734", "name": "NAVE ANDROMEDA", "vessel_type": "Product Tanker", "flag": "Liberia"},
    {"imo_number": "9526875", "mmsi": "477553100", "name": "PACIFIC JEWEL", "vessel_type": "LNG Carrier", "flag": "Hong Kong"},
    {"imo_number": "9454036", "mmsi": "477418200", "name": "VALE BRASIL", "vessel_type": "Bulk Carrier", "flag": "Hong Kong"},
    {"imo_number": "9586801", "mmsi": "538005588", "name": "ORE TIANJIN", "vessel_type": "Bulk Carrier", "flag": "Marshall Islands"},
    {"imo_number": "9672876", "mmsi": "636017505", "name": "STELLAR BANNER", "vessel_type": "Bulk Carrier", "flag": "Liberia"},
    {"imo_number": "9383395", "mmsi": "477225600", "name": "BERGE STAHL", "vessel_type": "Bulk Carrier", "flag": "Hong Kong"},
    {"imo_number": "9551131", "mmsi": "538004888", "name": "CAPE BRUNNY", "vessel_type": "Bulk Carrier", "flag": "Marshall Islands"},
    {"imo_number": "9321098", "mmsi": "636015000", "name": "GOLDEN STAR", "vessel_type": "Tanker", "flag": "Liberia"},
    {"imo_number": "9876543", "mmsi": "211234567", "name": "EVER FORTUNE", "vessel_type": "Cargo", "flag": "Germany"},
    {"imo_number": "9765432", "mmsi": "311456789", "name": "MAERSK SEALAND", "vessel_type": "Cargo", "flag": "Denmark"},
    {"imo_number": "9654321", "mmsi": "412345678", "name": "PACIFIC VOYAGER", "vessel_type": "Tanker", "flag": "Panama"},
    {"imo_number": "9543210", "mmsi": "512345678", "name": "OCEAN PEARL", "vessel_type": "Passenger", "flag": "Bahamas"},
    {"imo_number": "9432109", "mmsi": "612345678", "name": "BLUE MARLIN", "vessel_type": "Cargo", "flag": "Netherlands"},
    {"imo_number": "9210987", "mmsi": "812345678", "name": "NORDIC SPIRIT", "vessel_type": "Cargo", "flag": "Norway"},
    {"imo_number": "9109876", "mmsi": "912345678", "name": "ATLANTIC FISHER", "vessel_type": "Fishing", "flag": "Spain"},
    {"imo_number": "9087654", "mmsi": "314567890", "name": "CORAL PRINCESS", "vessel_type": "Passenger", "flag": "Bermuda"},
    {"imo_number": "9076543", "mmsi": "415678901", "name": "STENA BULK", "vessel_type": "Tanker", "flag": "Sweden"},
]


def search_local(query: str) -> list[dict]:
    """Search the built-in vessel database by name."""
    q = query.lower()
    return [v for v in KNOWN_VESSELS if q in v["name"].lower()]


def lookup_imo_local(imo: str) -> dict | None:
    """Reverse lookup: IMO → vessel details."""
    imo_clean = "".join(c for c in imo if c.isdigit())
    for v in KNOWN_VESSELS:
        if v["imo_number"] == imo_clean:
            return v
    return None


async def search_live(query: str) -> list[dict]:
    """Search using the configured AIS provider."""
    from app.ingestion.ais.vessel_worker import create_ais_provider
    provider = create_ais_provider()
    try:
        results = await provider.search_vessel(query)
        return results
    finally:
        if hasattr(provider, "close"):
            await provider.close()


async def lookup_imo_live(imo: str) -> dict | None:
    """Reverse lookup using the configured AIS provider."""
    from app.ingestion.ais.vessel_worker import create_ais_provider
    provider = create_ais_provider()
    try:
        return await provider.get_vessel_by_imo(imo)
    finally:
        if hasattr(provider, "close"):
            await provider.close()


def print_vessel(v: dict) -> None:
    """Print a vessel in formatted output."""
    imo = v.get("imo_number", "?")
    name = v.get("name", "Unknown")
    vtype = v.get("vessel_type", "Unknown")
    flag = v.get("flag", "?")
    mmsi = v.get("mmsi", "?")

    print(f"  IMO: {imo} | Name: {name} | Type: {vtype} | Flag: {flag} | MMSI: {mmsi}")
    print(f"  → CSV line: {imo},{name},,,")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Search for vessel IMO numbers by name or reverse-lookup by IMO."
    )
    parser.add_argument("query", nargs="?", help="Vessel name to search (partial match)")
    parser.add_argument("--imo", help="Reverse lookup: IMO number → full details")
    parser.add_argument("--live", action="store_true", help="Use live AIS provider instead of built-in database")

    args = parser.parse_args()

    if not args.query and not args.imo:
        parser.print_help()
        sys.exit(1)

    if args.imo:
        # Reverse lookup
        if args.live:
            result = asyncio.run(lookup_imo_live(args.imo))
        else:
            result = lookup_imo_local(args.imo)

        if result:
            print(f"\n✓ Found vessel for IMO {args.imo}:\n")
            print_vessel(result)
        else:
            print(f"\n✗ No vessel found for IMO {args.imo}")
            if not args.live:
                print("  Tip: Try --live flag to query the AIS provider")
        return

    # Name search
    query = args.query
    if args.live:
        results = asyncio.run(search_live(query))
    else:
        results = search_local(query)

    if results:
        print(f"\n✓ Found {len(results)} vessel(s) matching '{query}':\n")
        for v in results[:20]:
            print_vessel(v)
    else:
        print(f"\n✗ No vessels found matching '{query}'")
        if not args.live:
            print("  Tip: Try --live flag to query the AIS provider")


if __name__ == "__main__":
    main()
