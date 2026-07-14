# BattleChain Confidence Pools — AUT934129MAX Contest Profile

This machine targets the live Cyfrin CodeHawks contest at
`https://codehawks.cyfrin.io/c/2026-07-battlechain-confidence-pools` using protocol source
`incjanta/confidence-pool` pinned locally at commit
`58e8ba4ce3f3277866e4926f3140e597f9554a1e`.

## Contest facts

- Window: 2026-07-09 12:00 UTC through 2026-07-16 12:00 UTC.
- Prize: 7.25 ETH total; 6 ETH for High/Medium and 1.25 ETH for Low.
- Size/tooling: 589 nSLOC, Foundry, Solidity 0.8.26, BattleChain EVM L2.
- CodeHawks accepts High, Medium, and Low. `Critical` is retained only as an internal search
  priority and must be submitted as High if proven.

## Exact code scope

- `src/ConfidencePool.sol`
- `src/ConfidencePoolFactory.sol`

BattleChain interfaces, other interfaces/libraries, mocks, tests, scripts, and dependencies are
context only. Standard ERC20 tokens are assumed; fee-on-transfer and rebasing tokens are not
supported attack premises.

## Trusted-role exclusion

Factory owner/upgrader, pool sponsor, moderator/DAO, SafeHarborRegistry, and attack-registry
controller are trusted within their documented powers. Reject any candidate that requires one of
them to act maliciously, sneakily, collusively, through a compromised key, or through an admin
mistake. Do not reject a genuine unprivileged role bypass or a defect caused by an ordinary honest
privileged action.

## Paid impact coverage

- Internal Critical / platform High: catastrophic direct drain, insolvency, or total core
  settlement failure.
- High: direct/nearly direct funds risk or severe core-function failure with sufficient likelihood.
- Medium: conditional/indirect funds risk or material persistent protocol functionality failure.
- Low: concrete reachable incorrect function/state behavior with minimal impact and no direct
  funds risk.

Gas, QA, informational, style-only, generic best-practice, and vague unproved reports are unpaid.
Every promoted issue must survive the accepted-design list in `docs/DESIGN.md` and have a precise
call/state sequence, impact/likelihood analysis, and preferably a Foundry PoC.

## Activation note

No runnable Python was edited. The unchanged loader still names `blueprints/portal_fund_reward.json`;
that configuration file has been replaced with the Confidence Pools blueprint. The explicit marker
`blueprints/confidence_pool_codehawks.json` records this compatibility alias.
