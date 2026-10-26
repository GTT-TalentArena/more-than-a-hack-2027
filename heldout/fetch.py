"""Download the DFL/IDSSE open data (Bassek et al., 2025; CC BY 4.0) from figshare, with MD5 checks.

    python -m heldout.fetch [--out DIR] [MATCH_ID ...]

The file list comes from the figshare API for a pinned article version, not from hard-coded URLs:
the download host kloppy 3.18 uses (springernature.figshare.com) now answers with a bot challenge.
Files already present with the right MD5 are skipped, so the command can be re-run.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request

ARTICLE = 28196177
VERSION = 1
API = "https://api.figshare.com/v2/articles/{}/versions/{}".format(ARTICLE, VERSION)
MATCHES = ("J03WMX", "J03WN1", "J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9")
# What each file name says it is: match information, raw events, raw observed positions.
KINDS = {"matchinformation": "meta", "events_raw": "events", "positions_raw_observed": "positions"}
CHUNK = 1 << 20


def default_dir():
    root = os.environ.get("GTT_SALIDAS") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "salidas")
    return os.path.join(root, "heldout", "dfl")


def file_list():
    with urllib.request.urlopen(API, timeout=60) as response:
        article = json.load(response)
    files = []
    for entry in article["files"]:
        match = re.search(r"DFL-MAT-(J03W\w\w)\.xml$", entry["name"])
        kind = next((k for key, k in KINDS.items() if key in entry["name"]), None)
        if match and kind:
            files.append(dict(match=match.group(1), kind=kind, name=entry["name"],
                              size=entry["size"], md5=entry["computed_md5"],
                              url=entry["download_url"]))
    return sorted(files, key=lambda f: (f["match"], f["kind"]))


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(entry, folder):
    path = os.path.join(folder, entry["name"])
    if os.path.exists(path) and md5(path) == entry["md5"]:
        return path, False
    partial = path + ".part"
    with urllib.request.urlopen(entry["url"], timeout=120) as response, open(partial, "wb") as out:
        for block in iter(lambda: response.read(CHUNK), b""):
            out.write(block)
    if md5(partial) != entry["md5"]:
        os.remove(partial)
        raise IOError("MD5 mismatch for {}".format(entry["name"]))
    os.replace(partial, path)
    return path, True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("matches", nargs="*", default=list(MATCHES), help="DFL match ids (default: all 7)")
    parser.add_argument("--out", default=default_dir(), help="cache folder (default: salidas/heldout/dfl)")
    args = parser.parse_args(argv)
    unknown = sorted(set(args.matches) - set(MATCHES))
    if unknown:
        parser.error("unknown match ids: " + ", ".join(unknown))
    os.makedirs(args.out, exist_ok=True)
    wanted = [f for f in file_list() if f["match"] in args.matches]
    manifest = []
    for entry in wanted:
        path, fresh = download(entry, args.out)
        print("{} {:<9} {:>7.1f} MB  {}".format("got " if fresh else "have", entry["kind"],
                                                 entry["size"] / 1e6, entry["name"]), flush=True)
        manifest.append({k: entry[k] for k in ("match", "kind", "name", "size", "md5")})
    with open(os.path.join(args.out, "manifest.json"), "w") as handle:
        json.dump({"article": ARTICLE, "version": VERSION, "licence": "CC BY 4.0", "files": manifest},
                  handle, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
