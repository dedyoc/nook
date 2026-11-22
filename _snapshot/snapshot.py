# Consistent copies of every SQLite database under one app's data directory (homelab ADR-045).
# Generalises Memos' snapshot (ADR-038): restic copies volumes at 03:00, but a live WAL-mode
# database copied file-by-file may not open. This uses SQLite's online backup API instead.
#
# Usage: python3 snapshot.py <data-dir>
# Writes <data-dir>/.snapshots/<same relative path>. Restore from there, never from the live file.
# Run as the app's own UID: opening a WAL database creates/writes its -shm file, and a -shm owned
# by another user locks the app out.
import os, sqlite3, sys, urllib.parse

MAGIC = b"SQLite format 3\x00"
SKIP_SUFFIXES = ("-wal", "-shm", "-journal", ".tmp")

root = os.path.abspath(sys.argv[1])
out_root = os.path.join(root, ".snapshots")
found, failed = 0, []

for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if os.path.join(dirpath, d) != out_root]
    for name in filenames:
        src_path = os.path.join(dirpath, name)
        if name.endswith(SKIP_SUFFIXES) or os.path.islink(src_path):
            continue
        try:
            with open(src_path, "rb") as fh:
                if fh.read(16) != MAGIC:
                    continue
        except OSError:
            continue
        found += 1
        rel = os.path.relpath(src_path, root)
        out = os.path.join(out_root, rel)
        tmp = out + ".tmp"
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if os.path.exists(tmp):
                os.remove(tmp)
            # mode=rw: never create an empty database where one was expected.
            src = sqlite3.connect("file:" + urllib.parse.quote(src_path) + "?mode=rw", uri=True, timeout=30)
            dst = sqlite3.connect(tmp)
            src.backup(dst)
            src.close()
            dst.execute("PRAGMA journal_mode=DELETE")   # one self-contained file
            result = dst.execute("PRAGMA integrity_check").fetchone()[0]
            dst.close()
            if result != "ok":
                raise RuntimeError("integrity_check: " + result)
            os.replace(tmp, out)                        # atomic: restic never sees half a file
            print("ok", rel, os.path.getsize(out), "bytes")
        except Exception as e:                          # keep going; fail the Job at the end
            failed.append(rel)
            print("FAILED", rel, e, file=sys.stderr)

print(f"{found} database(s), {len(failed)} failed, under {root}")
# Zero databases is not an error: most apps create theirs on first login.
sys.exit(1 if failed else 0)
