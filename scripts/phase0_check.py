"""Phase 0 recon checks. Prints PASS / FAIL / SKIP per item. Nothing here is a substitute
for reading the hackathon repo; use it to confirm access and capture facts for PROGRESS.md."""
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def report(name: str, status: str, detail: str = "") -> None:
    print(f"[{status:<4}] {name}" + (f": {detail}" if detail else ""))


def check_python() -> None:
    ok = sys.version_info >= (3, 12)
    report("python >= 3.12", "PASS" if ok else "FAIL", sys.version.split()[0])


def check_env() -> None:
    for var in ("AWS_REGION", "BEDROCK_MODEL_ID", "DECIDER_URL"):
        report(f"env {var}", "PASS" if os.getenv(var) else "SKIP", "set" if os.getenv(var) else "not set")


def check_strands() -> None:
    try:
        import strands  # noqa: F401
        report("strands importable", "PASS")
    except ImportError:
        report("strands importable", "SKIP", "install the package named in the hackathon repo")


def check_bedrock() -> None:
    model = os.getenv("BEDROCK_MODEL_ID")
    if not model:
        return report("bedrock converse call", "SKIP", "BEDROCK_MODEL_ID not set")
    try:
        import boto3
        client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        resp = client.converse(
            modelId=model,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: ok"}]}],
            inferenceConfig={"maxTokens": 10},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        report("bedrock converse call", "PASS", text.strip())
    except Exception as e:  # noqa: BLE001
        report("bedrock converse call", "FAIL", f"{type(e).__name__}: {e}")


def check_decider() -> None:
    url = os.getenv("DECIDER_URL")
    if not url:
        return report("decider call", "SKIP", "DECIDER_URL not set")
    try:
        import requests
        # TODO: replace this payload with the typed-question format from the hackathon repo.
        r = requests.post(url, json={"question": "Would a thoughtful teammate interject right now?",
                                     "context": "Test failed 2s ago; developer has not opened the traceback."},
                          timeout=15)
        report("decider call", "PASS" if r.ok else "FAIL", f"HTTP {r.status_code} {json.dumps(r.text[:200])}")
        print("  Record the real request/response shape in PROGRESS.md.")
    except Exception as e:  # noqa: BLE001
        report("decider call", "FAIL", f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    check_python()
    check_env()
    check_strands()
    check_bedrock()
    check_decider()
