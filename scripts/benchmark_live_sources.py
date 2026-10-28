"""Measure live source coverage and latency; not a statistical accuracy claim.

API_SERVICE_TOKEN is read from the environment and is never written to reports.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import httpx

CASES = [
    ("전쟁과 평화", None), ("인간의 굴레에서", None),
    ("데미안", None), ("사피엔스", None), ("어린 왕자", None),
    ("죄와 벌", None), ("1984", None), ("Clean Code", None),
    ("9788937460111", ["aladin", "kyobo", "yes24", "sarak"]),
    ("zxqv없는책987654", ["aladin", "kyobo", "yes24", "sarak"]),
]


async def benchmark(base, output, cases=None, concurrency=2):
    semaphore = asyncio.Semaphore(concurrency)
    headers = {"x-api-token": os.environ["API_SERVICE_TOKEN"]} if os.getenv("API_SERVICE_TOKEN") else {}
    if os.getenv("DEPLOYMENT_BYPASS"):
        headers["x-vercel-protection-bypass"] = os.environ["DEPLOYMENT_BYPASS"]
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=65) as client:
        async def search(case):
            query, platforms = case
            async with semaphore:
                start = time.perf_counter()
                events, first, event = [], None, None
                async with client.stream("POST", "/api/search/stream", json={"query":query, "platforms":platforms, "force_refresh":True}) as response:
                    response.raise_for_status()
                    if not response.headers.get('content-type','').startswith('text/event-stream'):
                        raise ValueError('Expected the search API stream, not a protection or HTML page')
                    async for line in response.aiter_lines():
                        if line.startswith("event: "):
                            event = line[7:]
                        elif line.startswith("data: "):
                            data = json.loads(line[6:])
                            elapsed = round(time.perf_counter() - start, 3)
                            if event == "rating" and first is None:
                                first = elapsed
                            events.append({"event":event, "data":data, "elapsed":elapsed})
                ratings = [e["data"] for e in events if e["event"] == "rating"]
                states = [e["data"] for e in events if e["event"] == "platform_status"]
                result = {"query":query, "first_seconds":first, "seconds":round(time.perf_counter()-start,3),
                          "ratings":ratings, "states":states,
                          "metrics":next((e["data"] for e in events if e["event"] == "metrics"), {}),
                          "done":any(e["event"] == "done" for e in events)}
                print(json.dumps({"query":query,"first":first,"seconds":result["seconds"],
                                  "scores":{r["platform"]:r["rating"] for r in ratings},
                                  "states":{s["platform"]:s["status"] for s in states},"metrics":result["metrics"]},ensure_ascii=False),flush=True)
                return result
        results = await asyncio.gather(*(search(case) for case in (cases or CASES)))
    Path(output).write_text(json.dumps({"at":datetime.now(timezone.utc).isoformat(), "base":base,
                                       "cases":results},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument('--cases-file',help='JSON array of objects with query and optional platforms')
    parser.add_argument('--concurrency',type=int,default=2,choices=range(1,4))
    args = parser.parse_args()
    cases=[(entry['query'],entry.get('platforms')) for entry in json.loads(Path(args.cases_file).read_text())] if args.cases_file else None
    asyncio.run(benchmark(args.base_url, args.output,cases,args.concurrency))
