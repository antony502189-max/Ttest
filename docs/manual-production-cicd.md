# Manual GitHub Actions deployment to production

This is an opt-in CI/CD release path. Merging to main **never deploys**.
GitHub Actions workflow: .github/workflows/manual-production-deploy.yml.

The release preflight reads every page of changed PR files and check runs. It
verifies the file count against PR metadata before deciding whether payment
checks are required; incomplete API results refuse deployment.
Production website: https://app.112233.es, VPS 169.58.147.65, host vmi3640228.

After a successful PR merge, the repository owner clicks GitHub Actions >
Production deployment (manual approval) > Run workflow, selects main,
ticks the required confirmation box, and manually triggers the run. The
workflow checks the exact latest main SHA and PR CI before any VPS access.
The production job uses GitHub Environment "production". Configuring a
required reviewer adds a second "Approve and deploy" action; this can be
performed by the initiating user when Prevent self-review is disabled.
GitHub's required-reviewer protection is supported for this PUBLIC repo;
it must be configured in repository settings, not by committing a YAML file.

## Quick operator path after setup

For a **new developer**, begin with the [Russian step-by-step deployment guide](deploy-quickstart-ru.md); do **not** repeat the SSH/bootstrap steps below for each release.

1. PR → passing checks → merge to `main`.
2. [Open the production workflow](https://github.com/antony502189-max/Ttest/actions/workflows/manual-production-deploy.yml) → **Run workflow** → select **main**, tick confirmation → **Run workflow**.
3. Verify **Confirm exact main commit and passing PR CI** is green.
4. If `production` displays **Waiting for review**, use **Review deployments → Approve and deploy**. **A user may approve their own run only when `Prevent self-review` is disabled** and they are configured as an environment reviewer.
5. Wait for **Deploy manually approved release to VPS** (the real remote release). Verify expected SHA, `status=success`, public `/build-info.json`, and test changed functionality.

**Do not update `main` during an in-progress deployment.** A stale approved SHA is rejected on the VPS. A merge does not deploy. A disconnected SSH session does not prove the systemd-managed release stopped. Avoid overlapping release/backup/rollback operations.

### Deployment approval modes

| GitHub environment configuration | What happens |
| --- | --- |
| Required reviewers **on** + Prevent self-review **off** + operator is listed | Operator can **launch and approve their own deployment**. |
| Required reviewers **on** + Prevent self-review **on** | A **different** listed reviewer must approve. |
| Required reviewers **off** | One manual **Run workflow** confirmation; deployment starts automatically after CI verification without a second approval. |
| Wait timer on | Adds a delay; not necessary for a normal owner-approved release. |

The two secrets are stored in **Settings → Environments → production → Environment secrets**, never as repository files. Branch restriction should permit only `main`; administrator bypass of protection rules should normally remain disabled. **The existing running website is a separate state from GitHub `main`.**

## Initial setup (one time, by the server/repository owner)

Do not bootstrap during an active VPS backup, deployment, rollback or
restore. Confirm no release flock is held and no deploy is still running.
Keep keys out of Git, Slack, tickets, screenshots, terminal recordings and
ChatGPT. GitHub Actions cannot set the following secrets by itself.

### A. Allow the VPS to fetch GitHub non-interactively (read-only)

This is a DIFFERENT credential from the GitHub Actions -> VPS SSH key.
On the VPS as root:

    install -d -m 700 /root/.ssh
    ssh-keygen -t ed25519 -f /root/.ssh/id_112233_github_read -N '' -C 112233-vps-read-only
    cat /root/.ssh/id_112233_github_read.pub

Copy ONLY that public key into the repository's GitHub Settings >
Deploy keys > Add deploy key. Keep "Allow write access" DISABLED.
Configure /root/.ssh/config with the host entry:

    Host github.com
      HostName github.com
      User git
      IdentityFile /root/.ssh/id_112233_github_read
      IdentitiesOnly yes

Pin/verify GitHub's own SSH host key against the independently published
GitHub SSH fingerprints before accepting it. Do NOT blindly trust the
first ssh-keyscan reply. Change server repo origin and verify:

    git -C /srv/112233.es/repo remote set-url origin git@github.com:antony502189-max/Ttest.git
    GIT_TERMINAL_PROMPT=0 git -C /srv/112233.es/repo fetch origin --prune --tags

If fetch fails, do not proceed to deployment. Do not insert a Personal
Access Token into the remote URL. Existing releases are not replaced here.

### B. Install the reviewed forced-command entrypoint on the VPS

Only after this PR has passed CI and been merged to main, on the VPS:

    git -C /srv/112233.es/repo fetch origin main
    git -C /srv/112233.es/repo show origin/main:deploy/manual-production-runner.sh > /tmp/112233-reviewed-runner.sh
    bash -n /tmp/112233-reviewed-runner.sh
    install -o root -g root -m 0700 /tmp/112233-reviewed-runner.sh /usr/local/sbin/112233-manual-production-deploy
    rm -f /tmp/112233-reviewed-runner.sh

The installed file is deliberately OUTSIDE the checked-out Git worktree.
It must not be writable by the SSH key owner. Reinstall only after
reviewing future revisions of the runner.

### C. Create a separate Actions -> VPS SSH key

Generate a NEW ed25519 keypair on your trusted personal computer using
ssh-keygen. For example on Windows PowerShell:

    ssh-keygen -t ed25519 -a 100 -f "$env:USERPROFILE\.ssh\112233-gh-actions" -C "112233-actions"

Use an empty passphrase for this dedicated non-interactive CI key only;
the key is restricted on the server and stored as a protected secret.
Copy the PUBLIC key (.pub) to the VPS and append exactly one authorized_keys
line for it, with the actual public key replacing the example AAAA...:

    command="/usr/local/sbin/112233-manual-production-deploy",restrict ssh-ed25519 AAAA... 112233-actions

Do this only for this key; preserve all existing operator SSH keys.
Set /root/.ssh mode 700 and /root/.ssh/authorized_keys mode 600.
The forced command permits only the verified deploy SHA, not an arbitrary
interactive root shell, uploads, forwarding or user-selected script.

Create the GitHub Environment "production" and put the PRIVATE half of
the Actions -> VPS key into this environment's secret named:
PRODUCTION_SSH_PRIVATE_KEY. Never copy the VPS -> GitHub read-only key here.

### D. Pin the real VPS SSH host key

From a trusted existing login to the VPS, check its sshd host public-key
fingerprint:

    ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub

Compare it with the public key to be pinned. Add the complete known_hosts
line for "169.58.147.65 ssh-ed25519 AAAA..." as environment secret:
PRODUCTION_SSH_KNOWN_HOSTS.

Do not use StrictHostKeyChecking=no. The workflow always enforces host-key
validation and cannot silently learn an unverified server identity.

### E. GitHub environment approval

Open GitHub repository > Settings > Environments > New environment.
Name it precisely "production". Restrict deployment branches/tags to main.
Configure Required reviewers, selecting your account (or a different
designated approver). **For self-approval**, include the launching user among
reviewers and disable **Prevent self-review**. If it is enabled, a different
reviewer must approve. Do not enable administrator bypass without a documented
reason; restrict deployment branches to `main`.
Save both environment secrets from sections C and D.

In a GitHub public repository such as this one, GitHub supports required
reviewers on common plans. The reviewer rule is a settings-level protection;
without configuring it, workflow_dispatch plus its confirmation checkbox
still ensures *manual*, not automatic, deployment.

## Everyday release

1. Create a PR, pass required CI and merge into main. A merge itself
   performs no production action.
2. Go to GitHub > Actions > Production deployment (manual approval) >
   Run workflow. Select main, tick the explicit confirmation and run.
3. The verify-release job checks the exact main SHA, its merged PR and
   successful security/static/full/mobile CI jobs; for PRs that changed
   source code or tests it additionally requires payment CI. A direct push
   to main without verified PR evidence will be rejected.
4. When an Environment reviewer is configured, open Review deployments,
   select production, and click Approve and deploy (self-approval is permitted
   only when Prevent self-review is off).
5. The deploy job uses restricted SSH and systemd-run to start a
   persistent server-owned release. The VPS still performs authenticated
   MinIO backup gating, encrypted PostgreSQL backup, Alembic upgrade,
   application Docker rebuild, public health and build SHA verification.
6. Confirm status=success, active symlink and the public build-info.json,
   then manually test changed functionality on a real browser/device.

The server release entrypoint uses systemd-run --wait with a fixed SHA,
so the server-side service can continue after an SSH interruption.
For diagnostics inspect the release unit using:

    systemctl status 112233-release-SHA
    journalctl -u 112233-release-SHA --no-pager -n 100

If disconnected or failed, do not start another release until the shared
flock, processes and release metadata are checked. Never delete locks,
PostgreSQL/MinIO volumes or backups.

The actual deploy engine remains deploy/deploy-release.sh with existing
stateful-image guards, backup authentication checks and application-only
rollback. Application rollback cannot reverse destructive business-data
migrations. Keep encrypted backups and recovery procedures operational.
