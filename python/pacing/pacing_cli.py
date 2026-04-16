#!/usr/bin/env python3
"""
Pacing CLI - Thin wrapper around PacingService.calculate_pacing() for subprocess invocation.

Usage:
    python pacing_cli.py --redis-url redis://localhost:6379 --campaign-id 123

Reads campaign state from Redis, runs calculate_pacing, writes updated multiplier
back to Redis, and prints JSON result to stdout.
"""

import argparse
import json
import sys
import os

import redis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pacing.pacing import PacingService


def main():
    parser = argparse.ArgumentParser(description="Run pacing calculation for a campaign")
    parser.add_argument("--redis-url", required=True, help="Redis connection URL (e.g., redis://localhost:6379)")
    parser.add_argument("--campaign-id", default=None, help="Campaign ID to calculate pacing for")
    parser.add_argument("--campaign-ids", default=None,
                        help="Comma-separated campaign IDs for batch mode (e.g., '1,2,3')")
    parser.add_argument("--all-active", action="store_true", help="Run pacing for all active campaigns")
    parser.add_argument("--sim-time", type=float, default=None,
                        help="Simulated Unix timestamp (overrides wall-clock time for evaluation tests)")
    args = parser.parse_args()

    client = redis.from_url(args.redis_url, decode_responses=False)
    service = PacingService(client)

    if args.all_active:
        campaign_ids = service.get_active_campaign_ids()
        results = []
        for cid in campaign_ids:
            result = service.calculate_pacing(cid, sim_time=args.sim_time)
            results.append({
                "campaign_id": cid,
                "multiplier": result.multiplier,
                "error_normalized": result.error_normalized,
                "p_term": result.p_term,
                "i_term": result.i_term,
                "status": result.status,
            })
        print(json.dumps(results))
    elif args.campaign_ids:
        cids = [cid.strip() for cid in args.campaign_ids.split(",") if cid.strip()]
        results = {}
        for cid in cids:
            result = service.calculate_pacing(cid, sim_time=args.sim_time)
            results[cid] = {
                "multiplier": result.multiplier,
                "error_normalized": result.error_normalized,
                "p_term": result.p_term,
                "i_term": result.i_term,
                "status": result.status,
            }
        print(json.dumps(results))
    else:
        if not args.campaign_id:
            parser.error("--campaign-id is required unless --all-active or --campaign-ids is used")
        result = service.calculate_pacing(args.campaign_id, sim_time=args.sim_time)
        output = {
            "campaign_id": args.campaign_id,
            "multiplier": result.multiplier,
            "error_normalized": result.error_normalized,
            "p_term": result.p_term,
            "i_term": result.i_term,
            "status": result.status,
            "debug": result.debug,
        }
        print(json.dumps(output))

    client.close()


if __name__ == "__main__":
    main()
