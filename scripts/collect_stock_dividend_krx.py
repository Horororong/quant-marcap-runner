"""Eight official cash-equity market-days, using the existing KRX_AUTH_KEY.

No update job, pip, data overwrite, retry, price correction or inferred base.
Whole raw replies stay in the evidence artifact; only two selected securities'
original API rows and hashes are transferred. A first auth/HTTP failure stops.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib import request, error, parse

DATES = ("20191226", "20191227", "20201228", "20201229")
MARKETS = (("stk_bydd_trd", "068270"), ("ksq_bydd_trd", "091990"))
MAX_BYTES = 2 * 1024 * 1024


class Stop(Exception):
    def __init__(self, kind, http=None):
        self.kind, self.http = kind, http


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise Stop("REDIRECT_BLOCKED")


def fetch(endpoint, dt, key):
    url = "https://data-dbg.krx.co.kr/svc/apis/sto/" + endpoint + "?basDd=" + dt
    req = request.Request(url, headers={"AUTH_KEY": key, "Accept": "application/json"})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=25) as response:
            return response.status, response.read(MAX_BYTES + 1)
    except error.HTTPError as exc:
        raise Stop("HTTP_FAILURE", exc.code) from None
    except Stop:
        raise
    except Exception:
        raise Stop("TRANSPORT_FAILURE") from None


def acquire(output, key, transport=fetch):
    output.mkdir(parents=True, exist_ok=False)
    state = {"status": "UNVERIFIED", "requests": 0, "retries": 0, "responses": [], "target_rows": [],
             "scope": "cash equities only;2 markets x4 dates; max8 requests; no index/derivative data or inferred base", "investment_approved": False}
    try:
        if not key or any(c.isspace() for c in key):
            raise Stop("AUTH_ENV_MISSING_OR_INVALID")
        for endpoint, security in MARKETS:
            for dt in DATES:
                state["requests"] += 1
                http, raw = transport(endpoint, dt, key)
                if http != 200:
                    raise Stop("HTTP_FAILURE", http)
                if len(raw) > MAX_BYTES:
                    raise Stop("RESPONSE_SIZE_LIMIT", http)
                if key.encode() in raw or parse.quote(key, safe="").encode() in raw:
                    raise Stop("CREDENTIAL_ECHO_BLOCKED", http)
                try:
                    data = json.loads(raw)
                except Exception:
                    raise Stop("INVALID_JSON", http) from None
                if key in json.dumps(data, ensure_ascii=False):
                    raise Stop("CREDENTIAL_ECHO_BLOCKED", http)
                name = endpoint + "_" + dt + ".json"
                (output / name).write_bytes(raw)
                rows = data.get("OutBlock_1")
                state["responses"].append({"file": name, "endpoint": "https://data-dbg.krx.co.kr/svc/apis/sto/" + endpoint,
                    "parameters": {"basDd": dt}, "http_status": http, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                if not isinstance(rows, list) or not rows:
                    raise Stop("NO_QUOTE_ROWS_OR_SERVICE_NOT_AUTHORIZED", http)
                if any(str(r.get("BAS_DD", "")).replace("/", "").replace("-", "") != dt for r in rows):
                    raise Stop("RESPONSE_DATE_MISMATCH", http)
                matched = [(i, r) for i, r in enumerate(rows) if r.get("ISU_CD") == security or r.get("ISU_SRT_CD") == security]
                if len(matched) != 1:
                    raise Stop("TARGET_IDENTITY_NOT_UNIQUE_OR_CODE_NAMESPACE_UNVERIFIED", http)
                index, row = matched[0]
                if any(field not in row for field in ["TDD_CLSPRC", "FLUC_RT"]):
                    raise Stop("REQUIRED_PRICE_FIELDS_MISSING", http)
                state["target_rows"].append({"security": security, "date": dt, "source_file": name,
                                             "source_row_index": index, "raw_api_row": row})
        state["status"] = "COMPLETE_OFFICIAL_PRICE_ROWS_ONLY"
    except Stop as exc:
        state["error"] = {"kind": exc.kind, "http_status": exc.http}
    except Exception as exc:
        state["error"] = {"kind": "VALIDATION_FAILURE", "type": type(exc).__name__}
    (output / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return state


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    state = acquire(args.output, os.environ.get("KRX_AUTH_KEY", "").strip())
    raw = json.dumps(state, ensure_ascii=False).encode()
    print("STAGE12_KRX_STATE_BASE64_BEGIN")
    text = base64.b64encode(raw).decode()
    for i in range(0, len(text), 2000):
        print(text[i:i + 2000])
    print("STAGE12_KRX_STATE_BASE64_END")
    print(json.dumps({"status": state["status"], "requests": state["requests"], "error": state.get("error"), "state_sha256": hashlib.sha256(raw).hexdigest()}))
    raise SystemExit(0 if state["status"] == "COMPLETE_OFFICIAL_PRICE_ROWS_ONLY" else 2)
