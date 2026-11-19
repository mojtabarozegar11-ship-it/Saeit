"""Read-only network head probe, no wallet, order, secrets or chain writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import urllib.request
import urllib.error

ORIGINS = {
    "publicnode": "https://tron-solidity-rpc.publicnode.com",
    "trongrid": "https://api.trongrid.io",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def probe(entry):
    name, origin = entry
    result = {"endpoint": name, "reachable": False, "fresh": False}
    try:
        req = urllib.request.Request(
            origin + "/walletsolidity/getnowblock", data=b"{}", method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=8) as response:
            result["reachable"] = response.status == 200
            if not result["reachable"] or response.headers.get_content_type() != "application/json":
                return result
            data = response.read(150001)
        if len(data) > 150000:
            return result
        head = json.loads(data)["block_header"]["raw_data"]
        height, stamp = head["number"], head["timestamp"]
        if type(height) is not int or height <= 0 or type(stamp) is not int:
            return result
        age = datetime.now(timezone.utc).timestamp() - stamp / 1000
        result["fresh"] = -30 <= age <= 180
        if result["fresh"]:
            result["height"] = height
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["error_type"] = type(exc).__name__
    return result


def main():
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(probe, ORIGINS.items()))
    heads = [r["height"] for r in results if r["fresh"]]
    print("MPW_TRON_HEADS_READONLY=" + json.dumps({
        "providers": results,
        "both_fresh_and_agree": len(heads) == 2 and abs(heads[0]-heads[1]) <= 100,
        "read_only": True,
        "operator_independence_attested": False,
        "payment_finality_proven": False,
        "release_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
