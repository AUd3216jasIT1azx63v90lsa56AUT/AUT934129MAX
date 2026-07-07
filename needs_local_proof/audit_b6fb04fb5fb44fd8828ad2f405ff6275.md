<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_891013b5-ace6-450f-9f57-ed2fb71f6f99?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
reward_extraction

## Exact Code Path

**file:** `src/Portal.sol`
**function:** `setTokenBeneficiary`
**symbols/lines:** lines 351–360

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

**file:** `src/PortalBase.sol`
**symbols/lines:** line 410 — `mapping(address => address) internal _tokenBeneficiaries;` [1](#0-0) [2](#0-1) 

## Attacker Path

**preconditions:**
- Attacker previously called `newTokenV*` and set themselves as beneficiary (stored in `_tokenBeneficiaries[token]`).
- The `PORTAL_ROLLER` implementation's `setTokenBeneficiary` function does **not** check `msg.sender == DEFAULT_ADMIN_ROLE` or `msg.sender == _tokenBeneficiaries[token]`. This is the critical unverified assumption — the Roller source is not present in this repository.

**attacker-controlled inputs:**
- `token`: any token address for which attacker was the original creator/beneficiary
- `newBeneficiary`: attacker-controlled address (or any address to redirect payouts)

**call sequence:**
1. Attacker calls `Portal.setTokenBeneficiary(token, attackerAddress)` as an unprivileged EOA.
2. Portal has **zero access control** at its dispatch layer — no `onlyRole`, no beneficiary check.
3. `_delegateToImpl(PORTAL_ROLLER)` executes the Roller's `setTokenBeneficiary` in Portal's storage context.
4. If the Roller also lacks a caller check, `_tokenBeneficiaries[token]` is overwritten with `attackerAddress`.
5. All future `claim`/`delegateClaim` LP-fee and beneficiary payouts route to `attackerAddress`. [1](#0-0) [3](#0-2) 

## Why Existing Checks Fail

`Portal.setTokenBeneficiary` carries **no** `onlyRole`, `onlyIfBitFlagsSet`, or beneficiary-equality guard before delegating. The entire access-control burden falls on the Roller implementation. [1](#0-0) 

Compare with `setBitFlags`, which correctly applies `onlyRole(DEFAULT_ADMIN_ROLE)` inline in Portal before any delegation. `setTokenBeneficiary` has no equivalent guard. [4](#0-3) 

The `BeneficiaryChanged` event is defined in the interface, confirming the function is intended to mutate `_tokenBeneficiaries`. [5](#0-4) 

**Critical gap:** The `PORTAL_ROLLER` contract source is **not present** in this repository (`src/` contains only `Portal.sol`, `PortalBase.sol`, `PortalCommon.sol`, interfaces, and libraries). Whether the Roller enforces `DEFAULT_ADMIN_ROLE` or a current-beneficiary check internally cannot be confirmed from available source. The entire finding pivots on this unverified assumption. 

## Rejection Checks

**expected behavior checked:** `setTokenBeneficiary` is listed as a `role_or_config_entrypoint` in the live context, implying it should be privileged — but the Portal source shows no role guard at the dispatch layer.

**prior report checked:** Not determinable from available source.

**README/NatSpec checked:** No NatSpec on `Portal.setTokenBeneficiary` beyond `@inheritdoc IRoller`. The `IRoller` ABI artifact exists at `out/IPortal.sol/IRoller.json` but its full content was not read.

**unsupported assumption checked:** The core assumption — that the Roller lacks an access control check — is **not confirmed** from available source. This is the single gate between NEEDS_LOCAL_PROOF and a confirmed finding.

## Local Proof Required

**test type:** Foundry fork test against BSC mainnet (proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`, block ≥ 108382650)

**test file to add:** `test/fork/SetTokenBeneficiaryAccessControl.t.sol`

**test setup:**
1. Fork BSC at latest block.
2. Identify a live token address from a recent `TokenCreated` event where `_tokenBeneficiaries[token] != address(0)`.
3. Create an unprivileged EOA (`attacker`) that does **not** hold `DEFAULT_ADMIN_ROLE` and is not the current beneficiary.

**call sequence:**
```solidity
vm.prank(attacker);
portal.setTokenBeneficiary(token, attacker);
```

**expected assertion:**
- **If vulnerable:** call succeeds, `BeneficiaryChanged` event emitted with `newBeneficiary == attacker`, and subsequent `claim(token)` from `attacker` receives payouts.
- **If protected:** call reverts (e.g., `AccessControl: account ... is missing role ...` or a custom error).

**failure condition:** If the call succeeds and `_tokenBeneficiaries[token]` is overwritten without `DEFAULT_ADMIN_ROLE`, the finding is confirmed as a reward-extraction vulnerability. If it reverts, the Roller has its own guard and the finding is rejected.

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

**File:** src/Portal.sol (L530-535)
```text
    function setBitFlags(uint256 flags) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 old = bitFlags;
        bitFlags = flags;

        emit BitFlagsChanged(old, flags);
    }
```

**File:** src/PortalBase.sol (L409-411)
```text
    /// @dev mapping from token to beneficiary, slot: 169
    mapping(address => address) internal _tokenBeneficiaries;

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

**File:** src/interfaces/IPortal.sol (L1066-1070)
```text
    /// @notice emitted when a token beneficiary is changed
    /// @param token The address of the token
    /// @param oldBeneficiary The previous beneficiary address
    /// @param newBeneficiary The new beneficiary address
    event BeneficiaryChanged(address token, address oldBeneficiary, address newBeneficiary);
```
