<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_35c8e2c1-5c38-4db3-8225-252000297843?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
reward_extraction

## Exact Code Path

file: `src/Portal.sol`
function: `recoverStuckDividend`
symbols/lines: lines 463–470

```solidity
function recoverStuckDividend(
    RecoverStuckDividendParams[] calldata /*params*/
)
    external
    override
{
    _delegateToImpl(PORTAL_TWEAK);
}
```

The `Portal.sol` entry point carries **no access-control modifier** before delegating. Compare with `setBitFlags` (line 530, `onlyRole(DEFAULT_ADMIN_ROLE)`) and `halt` (lines 543–551, explicit `GUARDIAN_ROLE` check): every other privileged function in `Portal.sol` enforces its role at the proxy layer. `recoverStuckDividend` does not. [1](#0-0) [2](#0-1) [3](#0-2) 

The role check, if it exists at all, must live entirely inside the `PORTAL_TWEAK` delegatecall target. The `PORTAL_TWEAK` source file is **not present** in the indexed repository (glob for `**/PortalTweak*` returned zero results), so the presence or absence of an `AUDITOR_ROLE` guard inside that module cannot be confirmed from the indexed source alone. [4](#0-3) 

`PortalBase.sol` defines `GUARDIAN_ROLE`, `TAX_MANAGER_ROLE`, `TAX_GUARDIAN_ROLE`, `TOKEN_FLAP_FEE_SETTER_ROLE`, and `MODERATOR_ROLE` as `public constant` bytes32 values — but **`AUDITOR_ROLE` is absent from `PortalBase.sol`**. Its 10 appearances are confined to `IPortal.sol` (interface only). This is consistent with the role being defined and checked only inside the unindexed `PORTAL_TWEAK` module, but it is also consistent with the role being defined there but never enforced on `recoverStuckDividend`.

## Attacker Path

**preconditions:**
- `PORTAL_TWEAK` implementation does not call `_checkRole(AUDITOR_ROLE, msg.sender)` (or equivalent) at the top of its `recoverStuckDividend` handler, OR the check is present but operates on a role that has been granted to `address(0)` / is trivially satisfiable.
- At least one dividend contract holds tokens belonging to legitimate holders.

**attacker-controlled inputs:**
- `RecoverStuckDividendParams[]` array: attacker sets `taxToken` to a live tax token whose dividend contract holds user balances, and sets the recipient field to an attacker-controlled address.

**call sequence:**
1. Attacker (unprivileged EOA) calls `Portal.recoverStuckDividend([{taxToken: victimToken, recipient: attacker, ...}])`.
2. `Portal.sol` performs no role check; calls `_delegateToImpl(PORTAL_TWEAK)`.
3. `PORTAL_TWEAK` executes in Portal's storage context; if no role guard is present, it calls `IDividend(dividendContract).emergencyWithdraw(recipient, amount)` (or equivalent), transferring tokens to the attacker.

## Why Existing Checks Fail

The `Portal.sol` wrapper applies **zero access control** before the delegatecall. The `_delegateToImpl` helper is a raw assembly delegatecall with no pre-call guard. [5](#0-4) 

If `PORTAL_TWEAK` also omits the role check (or checks a role that is trivially held), there is no defense-in-depth. The pattern used by every other sensitive function — placing `onlyRole(...)` on the `Portal.sol` stub — is absent here.

## Rejection Checks

**expected behavior checked:** `recoverStuckDividend` is documented as an emergency recovery path for *stuck* funds, not a general withdrawal. Calling it on a live dividend contract with active holders would violate the protocol's stated invariant.

**prior report checked:** Not determinable from indexed source alone; no NatSpec or README text visible in the indexed files explicitly marks this as a known issue.

**README/NatSpec checked:** No NatSpec on the `Portal.sol` stub for `recoverStuckDividend`; the interface definition in `IPortal.sol` references `AUDITOR_ROLE` but the stub carries no `@dev` guard note.

**unsupported assumption checked:** The critical unsupported assumption is that `PORTAL_TWEAK` lacks the role check. This cannot be confirmed without the module source. The finding is plausible but not proven.

## Local Proof Required

**test type:** Foundry fork test against BSC mainnet (block 108382650)

**test file to add:** `test/RecoverStuckDividendAccessControl.t.sol`

**test setup:**
1. Fork BSC at the live block; bind `Portal` proxy at `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`.
2. Identify a live tax token with a non-zero dividend contract balance (query `DividendEmergencyWithdrawn` / `TokenDividendTokenUpdated` events to find a candidate).
3. Construct a `RecoverStuckDividendParams[]` array targeting that token with `recipient = address(attacker)`.

**expected assertion (vulnerability present):**
```solidity
vm.prank(attacker); // unprivileged EOA
portal.recoverStuckDividend(params); // must NOT revert
assertGt(IERC20(dividendToken).balanceOf(attacker), 0);
```

**expected assertion (vulnerability absent):**
```solidity
vm.prank(attacker);
vm.expectRevert(); // AccessControl revert
portal.recoverStuckDividend(params);
```

**failure condition:** If the call succeeds and transfers tokens to the attacker, the finding is confirmed as HIGH. If it reverts with an access-control error originating inside `PORTAL_TWEAK`, the finding is rejected.

### Citations

**File:** src/Portal.sol (L463-470)
```text
    function recoverStuckDividend(
        RecoverStuckDividendParams[] calldata /*params*/
    )
        external
        override
    {
        _delegateToImpl(PORTAL_TWEAK);
    }
```

**File:** src/Portal.sol (L530-535)
```text
    function setBitFlags(uint256 flags) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 old = bitFlags;
        bitFlags = flags;

        emit BitFlagsChanged(old, flags);
    }
```

**File:** src/Portal.sol (L543-551)
```text
    function halt() external override {
        // only guardian can halt the portal
        if (!(hasRole(GUARDIAN_ROLE, msg.sender) || hasRole(DEFAULT_ADMIN_ROLE, msg.sender))) {
            revert NotGuardian(msg.sender);
        }
        uint256 old = bitFlags;
        bitFlags = 0;
        emit BitFlagsChanged(old, 0);
    }
```

**File:** src/PortalBase.sol (L137-151)
```text
    /// guardian role
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    /// tax manager role - can update tax token addresses
    bytes32 public constant TAX_MANAGER_ROLE = keccak256("TAX_MANAGER_ROLE");

    /// tax guardian role - can change market wallet on V2/V3 tax tokens and update V1 tax splitter addresses
    bytes32 public constant TAX_GUARDIAN_ROLE = keccak256("TAX_GUARDIAN_ROLE");

    /// token flap fee setter role - can set fee profile for tokens
    bytes32 public constant TOKEN_FLAP_FEE_SETTER_ROLE = keccak256("TOKEN_FLAP_FEE_SETTER_ROLE");

    /// moderator role - can manage blocked spammers
    bytes32 public constant MODERATOR_ROLE = keccak256("MODERATOR_ROLE");

```

**File:** src/PortalBase.sol (L831-843)
```text
    function _delegateToImpl(address impl) internal {
        if (impl == address(0)) {
            revert FeatureDisabled();
        }
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }
```
