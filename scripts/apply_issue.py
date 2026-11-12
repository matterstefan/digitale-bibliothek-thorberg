#!/usr/bin/env python3
"""Apply a reviewed Thorberg edit proposal to data and the embedded site data.

Executed by the GitHub Action after the repository owner comments /übernehmen.
Only JSON data is parsed; no code from the issue is ever executed.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "daten.json"
INDEX = ROOT / "index.html"
RECORDS_PATTERN = re.compile(
    r'(<script id="records" type="application/json">)(.*?)(</script>)', re.S
)
PROPOSAL_PATTERN = re.compile(r"<!-- THORBERG_EDIT_V1\s*(\{.*?\})\s*END_THORBERG_EDIT_V1 -->", re.S)
MAX_ISSUE_BODY = 100_000


def request(url, method="GET", payload=None):
    token = os.environ["GH_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "thorberg-review-automation",
    }
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=30) as response:
        return json.load(response)


def issue_api():
    repo = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Unexpected repository")
    number = int(os.environ["ISSUE_NUMBER"])
    return f"https://api.github.com/repos/{repo}/issues/{number}", number


def read_proposal(body):
    if not isinstance(body, str) or len(body) > MAX_ISSUE_BODY:
        raise ValueError("Issue body invalid or too large")
    matches = PROPOSAL_PATTERN.findall(body)
    if len(matches) != 1:
        raise ValueError("No unique structured edit proposal found; create a new proposal using the updated form")
    proposal = json.loads(matches[0])
    if not isinstance(proposal, dict) or proposal.get("schema") != "thorberg-edit-proposal-v1":
        raise ValueError("Unrecognized proposal schema")
    if not isinstance(proposal.get("record_id"), int):
        raise ValueError("Invalid record id")
    changes = proposal.get("changes")
    if not isinstance(changes, dict) or not (1 <= len(changes) <= 30):
        raise ValueError("No valid changes")
    return proposal


def validate_values(values):
    if not isinstance(values, list) or len(values) > 100:
        raise ValueError("Invalid value list")
    for v in values:
        if not isinstance(v, dict) or set(v) != {"type", "text", "url", "label"}:
            raise ValueError("Invalid field value")
        if v["type"] not in ("literal", "uri") or not isinstance(v["label"], str):
            raise ValueError("Invalid type or label")
        if len(v["label"]) > 250:
            raise ValueError("Label too long")
        if v["type"] == "literal":
            if not isinstance(v["text"], str) or v["url"] is not None:
                raise ValueError("Invalid literal value")
        else:
            if v["text"] is not None or not isinstance(v["url"], str) or not re.match(r"^https?://", v["url"], re.I):
                raise ValueError("Invalid URL value")
        if len(str(v.get("text") or v.get("url") or "")) > 20_000:
            raise ValueError("Field value too large")


def parse_dimensions(values):
    """The first literal is the measurement; further literals may explain its provenance.

    Keep commentary in the original field values, but never use it as
    measurements for the size visualisation. Partial heights remain unscaled.
    """
    if not values:
        return "", None
    if values[0]["type"] != "literal":
        raise ValueError("The first dimension value must be text")
    if any(v["type"] != "literal" for v in values[1:]):
        raise ValueError("Dimension notes must be text")
    text = values[0]["text"].strip()
    if not text:
        return "", None
    parts = re.split(r"\s*[x×]\s*", text, flags=re.I)
    if len(parts) == 3 and all(re.fullmatch(r"\d+(?:[,.]\d+)?", p) for p in parts):
        nums = [float(p.replace(",", ".")) for p in parts]
        if not all(0 < v <= 200 for v in nums):
            raise ValueError("Measurements out of plausible range")
        return text, nums
    if re.fullmatch(r"\d+(?:[,.]\d+)?\s*cm\s*hoch", text, flags=re.I):
        return text, None
    raise ValueError("Measurements need height x width x depth (cm), or a documented height such as '38 cm hoch'")


def literal_first(values):
    if not values:
        return ""
    if values[0]["type"] != "literal":
        raise ValueError("Main display field must be text")
    return values[0]["text"]


def apply(data, proposal):
    match = [r for r in data if r["id"] == proposal["record_id"]]
    if len(match) != 1:
        raise ValueError("Record not found or duplicated")
    record = match[0]
    if record["signature"] != proposal.get("signature"):
        raise ValueError("Signature differs from the reviewed proposal")
    if record["bibliography"] != proposal.get("original_title"):
        raise ValueError("Title differs from the reviewed proposal")
    fields = record["fields"]
    for key, item in proposal["changes"].items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*:[A-Za-z][A-Za-z0-9_]*", key):
            raise ValueError("Invalid field key")
        if key == "bibo:number":
            raise ValueError("Historical signature changes require manual review of group and sorting")
        if not isinstance(item, dict) or set(item) != {"before", "after"}:
            raise ValueError("Invalid change")
        before, after = item["before"], item["after"]
        validate_values(before)
        validate_values(after)
        if fields.get(key, []) != before:
            raise ValueError(f"Field {key} changed since the proposal was submitted; no data written")
        if before == after:
            raise ValueError(f"No change to field {key}")
    # Apply only after every changed field has passed the old-value checks.
    for key, item in proposal["changes"].items():
        after = item["after"]
        if after:
            fields[key] = after
        else:
            fields.pop(key, None)
    if "crm:P40_observed_dimension" in proposal["changes"]:
        record["dimensions"], record["dimension_values"] = parse_dimensions(fields.get("crm:P40_observed_dimension", []))
    for key, prop in (("bibo:owner", "owner"), ("bibo:locator", "shelfmark"), ("bibo:content", "bibliography")):
        if key in proposal["changes"]:
            record[prop] = literal_first(fields.get(key, []))
    return record


def requested_issue_numbers():
    """One issue with /übernehmen, or an explicit numbered batch."""
    trigger = int(os.environ["ISSUE_NUMBER"])
    command = os.environ.get("APPROVAL_COMMENT", "").strip()
    if not re.fullmatch(r"/übernehmen(?: [1-9]\d*)*", command):
        raise ValueError("Expected /übernehmen or /übernehmen 4 5 6")
    parts = command.split()
    numbers = [trigger] if len(parts) == 1 else [int(x) for x in parts[1:]]
    if len(numbers) > 20 or len(set(numbers)) != len(numbers):
        raise ValueError("Too many or duplicate issue numbers")
    if trigger not in numbers:
        raise ValueError("The issue containing the approval comment must be included in the batch")
    return numbers


def write_files(proposals):
    data = json.loads(DATA.read_text(encoding="utf-8"))
    index = INDEX.read_text(encoding="utf-8")
    match = RECORDS_PATTERN.search(index)
    if not match:
        raise ValueError("Cannot find embedded site data")
    site_data = json.loads(match.group(2))
    if data != site_data:
        raise ValueError("daten.json and index.html disagree; changes need manual inspection")
    # Validate all proposals in memory before writing either file.
    for number, proposal in proposals:
        record = apply(data, proposal)
        print(f"Issue #{number}: validated {record['id']} ({record['signature']})")
    # JSON in HTML script must not contain a closing script tag from untrusted text.
    data_text = json.dumps(data, ensure_ascii=False, indent=2)
    html_data = data_text.replace("<", "\\u003c")
    new_index = index[:match.start(2)] + html_data + index[match.end(2):]
    assert json.loads(RECORDS_PATTERN.search(new_index).group(2)) == data
    DATA.write_text(data_text + "\n", encoding="utf-8")
    INDEX.write_text(new_index, encoding="utf-8")
    print(f"All {len(proposals)} proposals applied to both files.")


def main():
    url, trigger = issue_api()
    numbers = requested_issue_numbers()
    if len(numbers) > 1:
        print("Batch approval requested: " + ", ".join(map(str, numbers)))
    prefix = url.rsplit("/", 1)[0]
    proposals = []
    for number in numbers:
        issue = request(f"{prefix}/{number}")
        if issue.get("pull_request") or issue.get("state") != "open":
            raise ValueError(f"Issue #{number} is not open or is a pull request")
        proposal = read_proposal(issue.get("body", ""))
        proposals.append((number, proposal))
    write_files(proposals)
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("issue_numbers=" + ",".join(map(str, numbers)) + "\n")
    print("Commit/push will be handled by the workflow.")




if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError) as exc:
        print(f"Cannot apply proposal: {exc}", file=sys.stderr)
        sys.exit(1)
