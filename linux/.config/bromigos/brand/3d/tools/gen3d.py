#!/usr/bin/env python3
"""Image -> GLB through nolgia's POST /v1/generate/3d (the CLI has no 3d verb yet).

    gen3d.py <concept.png> <out.glb> [--model hunyuan3d-v3|trellis] [--texture]

Uploads the concept with `nolgia assets upload`, submits the job with the bearer
from `nolgia auth token` (never printed), waits, downloads the GLB, and appends a
line to ../generations.jsonl (job id, asset id, model, credits) so every spend is
tracked next to the models.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

API = os.environ.get("NOLGIA_API_URL", "https://api.nolgia.ai").rstrip("/") + "/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "generations.jsonl")
PRICE = {("hunyuan3d-v3", False): 13, ("hunyuan3d-v3", True): 21, ("trellis", True): 2}


def token():
    return subprocess.run(["nolgia", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def call(method, path, body=None, tok=None, timeout=120):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--model", default="hunyuan3d-v3")
    ap.add_argument("--texture", action="store_true")
    a = ap.parse_args()
    texture = a.texture or a.model == "trellis"
    up = subprocess.run(["nolgia", "--json", "assets", "upload", a.image], capture_output=True, text=True, check=True)
    asset = json.loads(up.stdout)
    aid = asset.get("id") or asset.get("asset", {}).get("id")
    tok = token()
    body = {"model": a.model, "image_asset_ids": [aid], "tags": ["bromigos", "holo"]}
    if a.model != "trellis":
        body["texture"] = texture
    job = call("POST", "/generate/3d", body, tok)
    jid = job["id"]
    print("job", jid, a.model, file=sys.stderr)
    t0 = time.time()
    while job.get("status") not in ("succeeded", "failed", "canceled"):
        time.sleep(5)
        try:
            job = call("GET", f"/jobs/{jid}/wait", tok=tok, timeout=90)
        except Exception:
            job = call("GET", f"/jobs/{jid}", tok=tok)
        if time.time() - t0 > 1500:
            sys.exit(f"timeout; follow job {jid}")
    if job["status"] != "succeeded":
        sys.exit(f"job {jid} {job['status']}: {job.get('failure')}")
    urllib.request.urlretrieve(job["asset"]["signed_url"], a.out)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "out": os.path.basename(a.out),
           "input": os.path.basename(a.image), "input_asset": aid, "job": jid,
           "asset": job["asset"]["id"], "model": a.model, "texture": texture,
           "credits": PRICE.get((a.model, texture)), "seconds": round(time.time() - t0)}
    with open(LEDGER, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
