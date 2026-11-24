# nook

Personal apps on my homelab: a single-node K3s cluster, reachable only over Tailscale. ArgoCD
deploys this repo into the `nook` namespace.

ArgoCD runs `kustomize build` on the repo root. The root `kustomization.yaml` lists one
directory per app, and each app's own `kustomization.yaml` lists its manifests. To add an app,
create its directory and add one line to the root list. To see exactly what gets deployed:

```bash
kubectl kustomize .
```

Runbooks (first run, restore, upgrades) live in the homelab repo, `docs/apps.md`.

## What every app has in common

- **One replica.** Apps backed by SQLite use `strategy: Recreate`, so two pods never write to
  the same database.
- **`enableServiceLinks: false`.** Otherwise Kubernetes adds `<SERVICE>_PORT` variables to the
  pod, and Memos mistakes `MEMOS_PORT` for its own setting.
- **Volumes use `local-path`, and deleting the PVC deletes the data.** `Prune=false` stops
  ArgoCD from deleting a PVC that gets renamed or removed in Git. The size is only a label.
- **No `tls:` block on Ingresses.** Traefik serves a `*.home.dedyoc.com` wildcard cert by
  default.
- **Nightly SQLite snapshots.** Each `<app>-snapshot` CronJob runs `_snapshot/snapshot.py`
  shortly before the 03:00 backup, so the backup gets a clean copy rather than a live WAL
  file. It runs as the app's own user: opening the database writes its `-shm` file, and one
  owned by another user locks the app out.
- **Images are pinned by digest.**

## Comments

A comment explains *why*, next to the line it's about. If the YAML already says it, or it's
covered above, it isn't repeated in the file.
