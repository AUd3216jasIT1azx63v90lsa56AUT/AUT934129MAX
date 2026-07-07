<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_c5de2b2f-9fde-4daa-b38f-004d2cd91cad?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
fund_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput` (lines 174–185), `_getSwapImplementation` (lines 54–76)
symbols/lines:

- `swapExactInput` — no reentrancy guard, only `onlyIfBitFlagsSet`; immediately delegates to `_getSwapImplementation` then `_delegateToImpl` [1](#0-0) 
- `_getSwapImplementation` — reads live `_packedTokenStates` storage to decide routing: `TokenStatus.DEX` → `PORTAL_DEX_ROUTER`, `TokenStatus.Tradable` → `PORTAL_TRADE_V2` [2](#0-1) 
- `_setTokenStatus` — bare storage write, no lock, no event ordering constraint [3](#0-2) 
- No `nonReentrant` / `ReentrancyGuard` found anywhere in `Portal.sol`, `PortalBase.sol`, or `PortalCommon.sol` (grep confirmed only Address.sol utilities match) [4](#0-3) 

## Attacker Path
**preconditions:**
- A token is in `TokenStatus.Tradable` with `circulatingSupply` just below `dexSupplyThresh`
- The migration flow in `PORTAL_TRADE_V2` makes an external call (to migrator/locker/router) **before** calling `_setTokenStatus(DEX)` — this ordering is the unverified pivot

**attacker-controlled inputs:**
- A malicious `recipient` contract that re-enters `swapExactInput` inside the external callback

**call sequence:**
1. Attacker calls `swapExactInput` with exact amount to push `circulatingSupply` ≥ `dexSupplyThresh`
2. `PORTAL_TRADE_V2` (via delegatecall) triggers migration; makes external call to migrator/locker
3. During that external call, attacker's contract re-enters `swapExactInput`
4. `_getSwapImplementation` reads storage — if status is still `Tradable` (not yet set to `DEX`), routes to `PORTAL_TRADE_V2`
5. Reentrant buy executes at bonding-curve price; tokens minted/transferred before DEX pool is funded

## Why Existing Checks Fail
The proxy-level `swapExactInput` has only `onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)` — no reentrancy lock. [5](#0-4) 

The routing guard in `_getSwapImplementation` is **conditional on ordering**: if `_setTokenStatus(DEX)` is called *before* the external liquidity-transfer call, a reentrant `swapExactInput` would route to `PORTAL_DEX_ROUTER` (which would revert on a non-existent pool) — effectively blocking the attack. But if `_setTokenStatus(DEX)` is called *after* the external call, the status is still `Tradable` during the callback window, routing goes to `PORTAL_TRADE_V2`, and the bonding-curve buy succeeds. [6](#0-5) 

**Critical gap:** `PORTAL_TRADE_V2` (the actual buy + migration implementation) is not present in this repository. The exact ordering of `_setTokenStatus(DEX)` relative to external migrator/locker calls cannot be confirmed from available source. This is the single unresolved pivot.

## Rejection Checks
**expected behavior checked:** Buying at bonding-curve price after migration is triggered is not expected behavior — it violates the `Tradable→DEX` invariant.

**prior report checked:** Not found in available source or NatSpec.

**README/NatSpec checked:** No NatSpec on `swapExactInput` or migration flow documents this ordering as intentional.

**unsupported assumption checked:** The attack requires `_setTokenStatus(DEX)` to be called *after* an external call in the migration path. This is the unverified assumption — it is plausible (CEI violations are common in migration flows) but not confirmed without `PORTAL_TRADE_V2` source.

## Local Proof Required
**test type:** Foundry fork test or unit test with mock migrator

**test file to add:** `test/ReentrancyMigration.t.sol`

**test setup:**
1. Deploy Portal with a mock `PORTAL_TRADE_V2` that: (a) checks `circulatingSupply >= dexSupplyThresh`, (b) calls an external migrator, (c) calls `_setTokenStatus(DEX)` *after* the external call
2. Deploy a mock migrator that re-enters `swapExactInput` during its callback
3. Bring a token to one-buy-away from `dexSupplyThresh`
4. Attacker calls `swapExactInput` with the threshold-crossing amount

**expected assertion:**
- If vulnerable: reentrant `swapExactInput` succeeds, attacker receives tokens at bonding-curve price after migration is triggered → assert attacker token balance > 0 and `circulatingSupply` exceeds `maxSupply` or reserve accounting is broken
- If protected: reentrant call reverts with `TokenNotTradable` or equivalent

**failure condition:** If the reentrant call succeeds and the attacker receives tokens at bonding-curve price while the DEX pool is unfunded, the invariant is broken and this is a confirmed fund-extraction path.

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

**File:** src/PortalBase.sol (L682-701)
```text
    /// @notice Modifier to check if the given bit mask is enabled in bitFlags
    modifier onlyIfBitFlagsSet(uint256 mask) {
        if (!_checkBitFlags(mask)) revert FeatureDisabled();
        _;
    }

    /// @dev check bit flags
    /// If a bit is off, means the feature is disabled
    function _checkBitFlags(uint256 mask) internal view returns (bool) {
        // We only check the bits in the mask are set
        // And ignore the bits that are not in the mask
        //
        //  -  mask => with only checking bits set
        //  -  mask ^ bitFlags =>
        //          XOR: all checking bits should be unset, if
        //          they are set in the bitFlags.
        //  - _ & mask, ignore the bits that are not in the mask
        //
        return (mask ^ bitFlags) & mask == 0;
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
