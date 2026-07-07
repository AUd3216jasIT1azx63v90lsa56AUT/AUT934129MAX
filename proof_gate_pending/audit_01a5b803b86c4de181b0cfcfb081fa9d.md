<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_98834227-e758-4ebe-b02a-8e339ccfe702?mode=deep -->
<!-- deepwiki_verdict: high_confidence_candidate -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
reward_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `delegateClaim`
symbols/lines: lines 159–171

```solidity
function delegateClaim(
    address /*token*/
)
    external
    override
    onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)   // ← only guard at Portal level
    returns (uint256, uint256)
{
    _delegateToImpl(PORTAL_ROLLER);
}
```

## Attacker Path
**preconditions:**
- A token has been launched to DEX and has accumulated LP fees
- `_tokenBeneficiaries[token]` is set to an attacker-controlled address (either the attacker is the original token creator/beneficiary, or `setTokenBeneficiary` was previously called to set it)
- The PORTAL_ROLLER delegatecall target does **not** enforce `ROLLER_ROLE` or `DEFAULT_ADMIN_ROLE` on `msg.sender` inside its `delegateClaim` logic

**attacker-controlled inputs:**
- `token` address pointing to a launched token whose beneficiary the attacker controls

**call sequence:**
1. Attacker calls `Portal.delegateClaim(token)` from an arbitrary EOA
2. Portal passes `onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)` (global halt is off)
3. `_delegateToImpl(PORTAL_ROLLER)` executes the roller's `delegateClaim` logic in Portal's storage context
4. If the roller has no caller role check, it collects LP fees and sends them to `_tokenBeneficiaries[token]`

## Why Existing Checks Fail
`src/Portal.sol` applies **only** `onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)` to `delegateClaim` — there is no `onlyRole(ROLLER_ROLE)` or `onlyRole(DEFAULT_ADMIN_ROLE)` guard at the Portal dispatcher level. [1](#0-0) 

The NatSpec in `IRoller` documents the intent: *"Only the roller or default admin can call this function."* [2](#0-1)  However, `ROLLER_ROLE` does not appear anywhere in the Portal, PortalBase, or PortalCommon source files — a `grep` for `ROLLER_ROLE` returns zero matches in `src/`. The role check is therefore entirely delegated to the PORTAL_ROLLER implementation contract.

**Critical gap:** The PORTAL_ROLLER implementation source is **not present** in this repository (`src/` contains only `Portal.sol`, `PortalBase.sol`, `PortalCommon.sol`, and interfaces).  Whether the roller enforces the caller role cannot be determined from the available source. If it does not, the Portal-level dispatcher provides no fallback guard.

## Rejection Checks
**expected behavior checked:** NatSpec explicitly states role restriction is required — this is not expected open access. [2](#0-1) 

**prior report checked:** Not determinable from available source.

**README/NatSpec checked:** NatSpec confirms the restriction is intended; the absence of enforcement at the Portal level is the gap.

**unsupported assumption checked:** The precondition "roller does not enforce the role" is unverifiable without the roller source — this is the core reason for NEEDS_LOCAL_PROOF rather than HIGH_CONFIDENCE_CANDIDATE.

## Local Proof Required
**test type:** Foundry fork test on BSC mainnet

**test file to add:** `test/DelegateClaimAccessControl.t.sol`

**test setup:**
1. Fork BSC at block 108382650 against proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`
2. Identify a token with a live DEX pool and accumulated LP fees (from `V4LPFeesCollected` events)
3. Note `_tokenBeneficiaries[token]` — if attacker is not the beneficiary, first check whether `setTokenBeneficiary` is also unguarded or use a token the attacker created
4. Call `Portal.delegateClaim(token)` from `address(0xDEAD)` (no roles)

**expected assertion:**
- If the call **reverts** with a role error → finding is invalid, REJECT
- If the call **succeeds** and LP fees are transferred to the beneficiary → confirm ETH/token delta; finding is valid

**failure condition:** Call succeeds and transfers value to beneficiary from an unprivileged EOA, confirming the roller has no caller role check.

### Citations

**File:** src/Portal.sol (L159-171)
```text
    function delegateClaim(
        address /*token*/
    )
        external
        override
        onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)
        returns (
            uint256, /*tokenAmount*/
            uint256 /*ethAmount*/
        )
    {
        _delegateToImpl(PORTAL_ROLLER);
    }
```

**File:** src/interfaces/IPortal.sol (L1888-1894)
```text
    /// @notice Allows a roller or default admin to claim LP fees on behalf of the beneficiary
    /// @param token The address of the token
    /// @return tokenAmount The amount of the token claimed
    /// @return quoteAmount The amount of quote token (or ETH) claimed
    /// @dev Only the roller or default admin can call this function.
    /// The claimed fee will be sent to the beneficiary of the token.
    function delegateClaim(address token) external returns (uint256 tokenAmount, uint256 quoteAmount);
```
