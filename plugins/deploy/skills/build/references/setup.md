# Deploy Plugin Setup

The `$deploy:build` command requires a GitHub Actions workflow in your repository that builds and pushes Docker images when a version tag is pushed.

## GitHub Actions Workflow

Create `.github/workflows/release.yaml` (or `release.yml`) triggered on `v*` tag pushes.

A minimal example:

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      # Add your test/lint steps here

  build-and-push:
    needs: [check]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      # Authenticate to your container registry
      # (example: Google Artifact Registry)
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v3
        with:
          credentials_json: ${{ secrets.GCP_SERVICE_ACCOUNT_KEY }}

      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker <region>-docker.pkg.dev

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: <region>-docker.pkg.dev/<project>/<repo>/<image>
          tags: |
            type=raw,value={{date 'YYYY.MM.DD'}}-{{sha}}
            type=ref,event=tag

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64
```

The `type=ref,event=tag` line produces an image tag matching the git tag (e.g., `v2026.04.04`), which can be used for explicit deploys to Cloud Run or Kamal. The date+SHA tag provides an immutable reference for debugging.

Adapt the registry authentication and image naming to your setup (GCP Artifact Registry, AWS ECR, Docker Hub, GitHub Container Registry, etc.).

## CHANGELOG.md

Optional — the command will create it if it doesn't exist. If you already have one, the new entry will be prepended after the first header line.
