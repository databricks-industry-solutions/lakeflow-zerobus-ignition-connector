# Deploy a Databricks App from GitHub (SDK)

End-to-end flow for creating an app that deploys from a Git repo and runs with the app’s service principal. The important part is attaching a **Git credential to the app’s service principal** (`principal_id`) so it can clone (including private) repos.

## Prerequisites

- Databricks SDK: `pip install databricks-sdk` (or use workspace SDK)
- GitHub repo URL and, for private repos, a **Personal Access Token (PAT)** with `repo` scope
- Workspace client (e.g. `WorkspaceClient()` with profile or env auth)

## Step 1: Create the app with a git repository

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import App, GitRepository

w = WorkspaceClient()

app = w.apps.create(
    app=App(
        name="my-app",
        description="My app deployed from GitHub",
        git_repository=GitRepository(
            url="https://github.com/org/repo",
            provider="gitHub"
        )
    )
).result()
```

## Step 2: Add a Git credential to the app’s service principal

The app gets an auto-created service principal. Use its ID when creating the Git credential so the **SP** can authenticate to GitHub (not your user). Without this, deploy from a private repo fails.

```python
# Get the SP ID from the app
sp_id = app.service_principal_id

# Create a git credential for that service principal
w.git_credentials.create(
    git_provider="gitHub",
    personal_access_token="ghp_xxxxxxxxxxxx",  # GitHub PAT
    git_username="my-github-user",
    principal_id=sp_id
)
```

`principal_id=sp_id` is what ties the credential to the app’s SP.

## Step 3: Deploy from Git

The app already has `git_repository` (url and provider) set. In the deployment request you must **only** pass the git reference (branch, tag, or commit) and optional `source_code_path`. Do not pass `git_repository` again in the deployment.

```python
from databricks.sdk.service.apps import (
    AppDeployment, GitSource, AppDeploymentMode
)

deployment = w.apps.deploy(
    app_name="my-app",
    app_deployment=AppDeployment(
        git_source=GitSource(
            branch="main",
            source_code_path="demo/app"   # optional: subpath within the repo
        ),
        mode=AppDeploymentMode.SNAPSHOT
    )
).result()
```

## SDK references

- **Git credentials:** `databricks.sdk.service.workspace.GitCredentialsAPI`  
  - `create(git_provider, personal_access_token=..., git_username=..., principal_id=...)`
- **Apps:** `databricks.sdk.service.apps`  
  - `App`, `GitRepository`, `AppDeployment`, `GitSource`, `AppDeploymentMode`

## Summary

1. Create app with `git_repository` (url, provider).
2. Call `git_credentials.create(..., principal_id=app.service_principal_id)` so the app’s SP can access the repo.
3. Call `apps.deploy(app_name, app_deployment=AppDeployment(git_source=..., mode=SNAPSHOT))` to deploy from Git.

For **zerobus-ignition-agl**, use the same flow with your repo URL and app name; ensure the repo has the app source (e.g. `demo/app`) and that the credential is set on the app’s service principal.
