# AUT934129MAX Deployment Target

Status: **prepared, not deployed**

- Repository owner/deployer: `AUd3216jasIT1azx63v90lsa56AUT`
- GitHub repository: `https://github.com/AUd3216jasIT1azx63v90lsa56AUT/AUT934129MAX`
- Git remote: `origin`
- Deployment branch: `master`
- Push behavior: current local branch to `origin`; `master` tracks `origin/master`
- Deployment mechanism: initial push by the repository owner, then manual
  `workflow_dispatch` runs under this repository's GitHub Actions identity.

## Required repository setup before dispatch

1. The repository must exist under `AUd3216jasIT1azx63v90lsa56AUT` and accept pushes from that
   account's credential.
2. Default branch must be `master` after the initial push.
3. Add the Actions secret `KEY_JSON` as a non-empty JSON object of DeepWiki corpus repository
   usernames mapped to their GitHub tokens. Do not commit `key.json`; `.gitignore` excludes it.
4. Keep Actions permissions able to write repository contents and dispatch subsequent workflows.
5. Run `Setup Repo` manually only after the configured tree is pushed. Do not dispatch setup from
   an old branch or old repository.

## Current audit identity

- Protocol source: `incjanta/confidence-pool`
- Contest: `2026-07-battlechain-confidence-pools`
- Active machine configuration: `blueprints/portal_fund_reward.json` compatibility path containing
  the BattleChain Confidence Pools blueprint
- Live context: `setup/live_context.json`
- DeepWiki repository index: intentionally empty until `Setup Repo` creates and indexes the new
  corpus repositories

No push or workflow dispatch was performed while creating this file.

## Verified pre-deployment blocker

The requested GitHub repository exists and currently exposes no remote refs. A no-write
`git push --dry-run --set-upstream origin master` was attempted on 2026-07-14 and GitHub rejected
the credential as belonging to `MjdkAko92IsxNC0sdeORcxaewE`, which does not have permission to
deploy this repository. The locally stored credential for `AUd3216jasIT1azx63v90lsa56AUT` is also
invalid, so it could not be selected.

Before deployment, authenticate this machine as `AUd3216jasIT1azx63v90lsa56AUT`, then repeat the
dry run and confirm GitHub identifies that account. Do not push using the currently active account.
