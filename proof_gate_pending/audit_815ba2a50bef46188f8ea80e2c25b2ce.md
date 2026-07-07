<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_934d70f8-5f1a-409d-a854-8aafa651e916?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
fund_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput`, `_getSwapImplementation`
symbols/lines: lines 54–76 (`_getSwapImplementation`), lines 174–185 (`swapExactInput`)

## Attacker Path
**preconditions:** Token is in `TokenStatus.Tradable`; `circulatingSupply` is just below `dexSupplyThresh`; attacker controls a receiver contract.

**attacker-controlled inputs:** `ExactInputParams` with `inputToken` = quote token, `outputToken` = target token; `msg.value` sized to push `circulatingSupply` past `dexSupplyThresh`.

**call sequence:**
1. Attacker calls `swapExactInput` with enough input to trigger migration.
2. Inside `PORTAL_TRADE_V2` (delegatecall), migration is initiated.
3. If the migration path makes an external call (to migrator/locker/router) **before** `_setTokenStatus(DEX)` is committed to storage, the token status is still `Tradable`.
4. Attacker's receiver contract re-enters `swapExactInput`.
5. `_getSwapImplementation` reads `state.status` from storage — still `Tradable` — and routes to `PORTAL_TRADE_V2`.
6. Attacker buys additional tokens at bonding-curve price; `circulatingSupply` and `reserve` are updated but the DEX pool has not yet been funded.

## Why Existing Checks Fail
The only status-based guard is in `_getSwapImplementation` (Portal.sol lines 66–75): it reads `state.status` from storage and routes to `PORTAL_DEX_ROUTER` only if status is already `DEX`. [1](#0-0) 

This is a natural guard **only if** `_setTokenStatus(DEX)` is called before any external callback in the migration path. If the ordering is reversed — external call first, then status update — the guard is bypassed. [2](#0-1) 

There is no `nonReentrant` modifier on `swapExactInput` in `Portal.sol`, and `_delegateToImpl` contains no reentrancy protection. [3](#0-2) [4](#0-3) 

The actual migration ordering — whether `_setTokenStatus(DEX)` precedes or follows the external migrator/locker call — lives entirely in `PORTAL_TRADE_V2` and the migrator contracts, which are **not present** in this repository. The source files available are only the proxy dispatcher and base storage helpers. 

## Rejection Checks
**expected behavior checked:** Routing to `PORTAL_DEX_ROUTER` after status flip is expected behavior; the question is whether the flip happens before or after the external call.

**prior report checked:** Not determinable from available source; no NatSpec or README comment addresses reentrancy ordering in the migration path.

**README/NatSpec checked:** No NatSpec on `swapExactInput` or `_getSwapImplementation` documents reentrancy safety or migration ordering guarantees.

**unsupported assumption checked:** The attack requires the migrator to make an external call before the status update — this is a concrete ordering question, not a speculative oracle or admin assumption. It is falsifiable by reading `PORTAL_TRADE_V2`.

## Local Proof Required
**test type:** Foundry fork test or unit test with mock migrator

**test file to add:** `test/ReentrancyMigration.t.sol`

**test setup:**
1. Deploy Portal with a mock `PORTAL_TRADE_V2` that, on the migration-trigger buy, calls an attacker-controlled migrator before invoking `_setTokenStatus(DEX)`.
2. The mock migrator calls back into `swapExactInput` on the Portal proxy.
3. Record the token output amount received in the reentrant call.

**expected assertion:** If the reentrant `swapExactInput` call succeeds and returns non-zero tokens at bonding-curve price (i.e., routes to `PORTAL_TRADE_V2` rather than reverting), the vulnerability is confirmed. If it reverts with `TokenNotTradable` or routes to `PORTAL_DEX_ROUTER` and fails due to unfunded pool, the natural guard holds.

**failure condition:** Reentrant call succeeds and attacker receives tokens at bonding-curve price after migration is triggered but before the DEX pool is funded — breaking the invariant that no bonding-curve trades occur after the `Tradable→DEX` transition.

### Citations

**File:** src/Portal.sol (L54-76)
```text
    function _getSwapImplementation(address inputToken, address outputToken)
        internal
        view
        returns (address implementation)
    {
        // Determine if this is a buy or sell
        bool isBuy = _quoteTokenConfigurations[inputToken].enabled == 1;
        address baseToken = isBuy ? outputToken : inputToken;

        // Get token state to check status
        PackedTokenStateV2 memory state = _getTokenState(baseToken);

        if (state.status == TokenStatus.DEX) {
            // Token is listed on DEX, use PortalDexRouter
            return PORTAL_DEX_ROUTER;
        } else if (state.status == TokenStatus.Tradable) {
            // Token is still in bonding curve, use PortalTradeV2
            return PORTAL_TRADE_V2;
        } else {
            // Invalid or other status, will fail in implementation
            return PORTAL_TRADE_V2; // Let PortalTradeV2 handle the error
        }
    }
```

**File:** src/Portal.sol (L174-185)
```text
    function swapExactInput(ExactInputParams calldata params)
        external
        payable
        override
        onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)
        returns (
            uint256 /* outputAmount */
        )
    {
        address implementation = _getSwapImplementation(params.inputToken, params.outputToken);
        _delegateToImpl(implementation);
    }
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

**File:** src/PortalBase.sol (L919-943)
```text
    function _setTokenStatus(address token, IPortalTypes.TokenStatus status) internal {
        if (token != address(uint160(uint256(uint160(token))))) revert DirtyBits();
        uint256 slot;
        assembly ("memory-safe") {
            mstore(0x0, token)
            mstore(0x20, _packedTokenStates.slot)
            slot := keccak256(0x0, 0x40)
        }
        uint256 packed;
        assembly ("memory-safe") {
            packed := sload(slot)
        }
        uint8 header = uint8(packed);
        if (header != PACKED_TOKEN_STATE_HEADER) {
            packed = (packed & ~uint256(0xff)) | uint8(status);
            assembly ("memory-safe") {
                sstore(slot, packed)
            }
        } else {
            packed = (packed & ~(uint256(0xff) << 8)) | (uint256(uint8(status)) << 8);
            assembly ("memory-safe") {
                sstore(slot, packed)
            }
        }
    }
```
