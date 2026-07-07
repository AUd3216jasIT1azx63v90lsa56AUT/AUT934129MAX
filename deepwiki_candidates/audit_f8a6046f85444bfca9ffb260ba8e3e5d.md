<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_c1bb08b3-6519-44eb-b433-e087d5fcb585?mode=deep -->
<!-- deepwiki_verdict: high_confidence_candidate -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
reward_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `setTokenBeneficiary`
symbols/lines: lines 351–360

```solidity
function setTokenBeneficiary(
    address, /*token*/
    address /* newBeneficiary */
)
    external
    override
{
    _delegateToImpl(PORTAL_ROLLER);
}
```

The Portal-level entry point carries **zero access control** — no `onlyRole(DEFAULT_ADMIN_ROLE)`, no `onlyIfBitFlagsSet`, no caller check of any kind. [1](#0-0) 

The call is forwarded via `_delegateToImpl(PORTAL_ROLLER)`, which executes the Roller's logic in Portal's storage context, writing directly to `_tokenBeneficiaries` (slot 169 in `PortalBase`). [2](#0-1) 

The `BeneficiaryChanged` event is declared in the interface and would be emitted on a successful change. [3](#0-2) 

## Attacker Path
**preconditions:**
- Attacker previously created a token and was set as its beneficiary (or knows any token address with a live beneficiary)
- `PORTAL_ROLLER.setTokenBeneficiary()` implementation (not present in this repo) does NOT enforce `msg.sender == DEFAULT_ADMIN_ROLE` or `msg.sender == _tokenBeneficiaries[token]`

**attacker-controlled inputs:**
- `token` = address of any launched token
- `newBeneficiary` = attacker-controlled address

**call sequence:**
1. Attacker calls `Portal.setTokenBeneficiary(token, attackerAddress)` with no special role
2. Portal forwards via `_delegateToImpl(PORTAL_ROLLER)` — no gate at Portal level
3. Roller executes in Portal's storage context; if it lacks its own caller check, it writes `_tokenBeneficiaries[token] = attackerAddress`
4. All future `claim`/`delegateClaim` LP-fee and beneficiary payouts route to attacker

## Why Existing Checks Fail
The Portal entry point has no `onlyRole`, no `onlyIfBitFlagsSet`, and no caller validation whatsoever. [1](#0-0)  The only possible guard is inside the Roller implementation itself. The Roller source (`PORTAL_ROLLER`) is **not present in this repository** — only the compiled ABI artifact `out/IPortal.sol/IRoller.json` exists. The `IRoller` interface definition in `IPortal.sol` does not show any access-control modifier on `setTokenBeneficiary`. Whether the Roller bytecode enforces a caller check cannot be confirmed from source alone and is the critical unknown.

## Rejection Checks
**expected behavior checked:** No NatSpec or README documents that token creators may freely update their own beneficiary post-launch; the invariant stated in the blueprint is that only `DEFAULT_ADMIN_ROLE` may change `_tokenBeneficiaries`.

**prior report checked:** Not found in available source files.

**README/NatSpec checked:** No NatSpec on `setTokenBeneficiary` in `Portal.sol` or `IPortal.sol` that documents caller restrictions.

**unsupported assumption checked:** The critical assumption — that the Roller lacks an internal caller check — cannot be confirmed from the indexed source. This is the sole reason for NEEDS_LOCAL_PROOF rather than HIGH_CONFIDENCE_CANDIDATE.

## Local Proof Required
**test type:** Foundry fork test against BSC mainnet (proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`, implementation `0xeb6c62d1885c421797d0c494e693c90d4b54125a`)

**test file to add:** `test/fork/SetTokenBeneficiaryUnauth.t.sol`

**test setup:**
1. Fork BSC at a recent block
2. Identify a live token address from a `TokenCreated` event where `_tokenBeneficiaries[token] != address(0)`
3. Use a fresh EOA (no roles) as `msg.sender`

**expected assertion (bug confirmed):**
```solidity
vm.prank(attacker);
portal.setTokenBeneficiary(token, attacker);
assertEq(portal._tokenBeneficiaries(token), attacker); // or BeneficiaryChanged emitted
```

**failure condition (bug absent):** Call reverts with an access-control error originating inside the Roller, proving the Roller enforces its own caller check despite Portal having none.

### Citations

**File:** src/Portal.sol (L351-360)
```text
    function setTokenBeneficiary(
        address,
        /*token*/
        address /* newBeneficiary */
    )
        external
        override
    {
        _delegateToImpl(PORTAL_ROLLER);
    }
```

**File:** src/PortalBase.sol (L409-410)
```text
    /// @dev mapping from token to beneficiary, slot: 169
    mapping(address => address) internal _tokenBeneficiaries;
```

**File:** src/interfaces/IPortal.sol (L1066-1070)
```text
    /// @notice emitted when a token beneficiary is changed
    /// @param token The address of the token
    /// @param oldBeneficiary The previous beneficiary address
    /// @param newBeneficiary The new beneficiary address
    event BeneficiaryChanged(address token, address oldBeneficiary, address newBeneficiary);
```
