<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_939f72a1-26d9-4731-a151-4bc99595876e?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

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
    address,  /*token*/
    address   /* newBeneficiary */
)
    external
    override
{
    _delegateToImpl(PORTAL_ROLLER);
}
```

The `Portal.sol` entry point carries **no** `onlyRole(DEFAULT_ADMIN_ROLE)` modifier and no other access-control guard before the delegatecall. [1](#0-0) 

The actual access-control logic — if any — must live inside the `PORTAL_ROLLER` implementation. The roller source file (`PortalRoller.sol` or equivalent) is **not present** in the indexed repository; only the following source files exist:



`_tokenBeneficiaries` is declared in `PortalBase.sol` at slot 169 as a plain `mapping(address => address)` with no inline guard. [2](#0-1) 

The `BeneficiaryChanged` event is defined in `IPortal.sol` and would be emitted by the roller on a successful change. [3](#0-2) 

## Attacker Path

**preconditions:**
- Attacker is the original token creator / current beneficiary for some live token.
- `PORTAL_ROLLER.setTokenBeneficiary()` either (a) has no role check, or (b) checks only `msg.sender == currentBeneficiary` (which the attacker satisfies) but does not restrict post-launch changes.

**attacker-controlled inputs:**
- `token` = address of a launched token whose beneficiary is the attacker.
- `newBeneficiary` = attacker-controlled address B.

**call sequence:**
1. `Portal.setTokenBeneficiary(token, B)` → `_delegateToImpl(PORTAL_ROLLER)` → roller writes `_tokenBeneficiaries[token] = B`.
2. All subsequent `claim` / `delegateClaim` / LP-fee distribution calls for `token` pay out to B.

## Why Existing Checks Fail

The `Portal.sol` wrapper has **zero** access-control modifier on `setTokenBeneficiary`. Whether the roller enforces `DEFAULT_ADMIN_ROLE` or any other guard is unknown because the roller implementation is absent from the indexed source. If the roller only checks `msg.sender == currentBeneficiary` (a common pattern for "let the creator update their own address"), an attacker who is the current beneficiary can freely redirect all future payouts. If the roller has no check at all, any caller can redirect any token's beneficiary.

## Rejection Checks

**expected behavior checked:** The NatSpec on `BeneficiaryChanged` and the interface do not document who is authorized to call `setTokenBeneficiary`; no "only admin" restriction is stated in any indexed file.

**prior report checked:** No prior report found in the indexed corpus.

**README/NatSpec checked:** No NatSpec on the `Portal.sol` wrapper function; the `IRoller` interface NatSpec (if any) is not in the indexed files.

**unsupported assumption checked:** The claim does not require oracle manipulation, malicious tokens, or admin key compromise — it is a pure access-control question on a public entrypoint.

## Local Proof Required

**test type:** Foundry fork test against BSC mainnet (block ≥ 108382650).

**test file to add:** `test/fork/SetTokenBeneficiaryAccessControl.t.sol`

**test setup:**
1. Fork BSC at the live block; use proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`.
2. Identify a live token address from a `TokenCreated` event where the creator is known (derive from event logs).
3. Impersonate the token creator (current beneficiary) as a non-admin EOA.

**expected assertion (vulnerability confirmed):**
```solidity
vm.prank(tokenCreator);
portal.setTokenBeneficiary(token, attacker);
assertEq(portal.getTokenBeneficiary(token), attacker); // or check BeneficiaryChanged event
```

**expected assertion (safe):**
```solidity
vm.prank(tokenCreator);
vm.expectRevert(); // any revert = access control present
portal.setTokenBeneficiary(token, attacker);
```

**failure condition:** If the call succeeds and `_tokenBeneficiaries[token]` is updated to the attacker address without `DEFAULT_ADMIN_ROLE`, the invariant is broken and all future `BeneficiaryClaimed` payouts for that token are redirected — constituting concrete reward extraction. The roller source must be obtained (via BSC explorer decompilation or verified source) to complete the source-level proof before promotion.

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
