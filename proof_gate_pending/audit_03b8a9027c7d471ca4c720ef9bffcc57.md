<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_b13d9b2f-7656-4978-af5b-e7283e262df3?mode=deep -->
<!-- deepwiki_verdict: high_confidence_candidate -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
fund_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput`
symbols/lines: `swapExactInput` (lines 174–185) → `_delegateToImpl(implementation)` → implementation contract buy logic → `_setTokenStatus` (2 call sites in `src/Portal.sol`) → external `luanchToDEX` call (selector `0x229f5f86`, defined in `IPortalMigrator`) [1](#0-0) [2](#0-1) [3](#0-2) 

## Attacker Path
**preconditions:**
- A token is in `TokenStatus.Tradable` with `circulatingSupply` just below `dexSupplyThresh`
- Attacker controls a contract that can receive ETH or ERC-20 callbacks (e.g., a malicious ERC-20 quote token with a hook, or a receive/fallback that re-enters Portal)
- No reentrancy guard exists anywhere in `src/Portal.sol`, `src/PortalBase.sol`, or `src/PortalCommon.sol` — confirmed by exhaustive grep for `nonReentrant`, `ReentrancyGuard`, `_status`, `_locked` [4](#0-3) 

**attacker-controlled inputs:**
- `ExactInputParams` with `inputToken = address(0)` (native BNB) or a malicious ERC-20 quote token, `outputToken = targetToken`, `inputAmount` sized to push `circulatingSupply >= dexSupplyThresh`

**call sequence:**
1. Attacker calls `swapExactInput(params)` on the Portal proxy
2. Portal delegates to the swap implementation; buy logic mints tokens, updates `circulatingSupply`, detects `circulatingSupply >= dexSupplyThresh`
3. Migration path calls `_setTokenStatus(token, TokenStatus.DEX)` and then makes an external call to the migrator (`luanchToDEX`)
4. **If** the external migrator call (or any intermediate ETH transfer / ERC-20 callback) occurs **before** `_setTokenStatus(DEX)` is written to storage, the attacker's contract re-enters `swapExactInput` for the same token
5. Re-entrant call sees `status == Tradable` (status not yet updated), buys additional tokens at bonding-curve price
6. Outer call completes migration; attacker holds tokens bought at pre-migration bonding-curve price that should have been locked into the DEX pool

## Why Existing Checks Fail
The only guard that would block a re-entrant buy is the `TokenStatus.DEX` check at the top of the buy path (which reverts with `TokenNotTradable` or `TokenAlreadyDEXed`). This guard is effective **only if** `_setTokenStatus(DEX)` is written to storage **before** any external call in the migration path. [5](#0-4) 

The critical ordering question — whether `_setTokenStatus(DEX)` precedes or follows the external `luanchToDEX` call — **cannot be resolved from the indexed source**. The `swapExactInput` entry point delegates entirely to an implementation address returned by `_getSwapImplementation`, and that implementation contract is **not among the verified source files** (`src/Portal.sol`, `src/PortalBase.sol`, `src/PortalCommon.sol`). The `luanchToDEX` selector (`0x229f5f86`) appears only in compiled ABI output and the interface, not in any indexed `.sol` implementation body. [6](#0-5) 

No `nonReentrant` modifier, `ReentrancyGuard`, or equivalent mutex was found anywhere in the source tree. If the implementation follows checks-effects-interactions (status written first, then external call), the attack is blocked. If the external call precedes the status write, the window is open.

## Rejection Checks
**expected behavior checked:** The invariant that no bonding-curve trades occur after migration is triggered is explicitly stated in the question and consistent with `TokenNotTradable`/`TokenAlreadyDEXed` errors — but only if the status write is atomic-before-external-call. [7](#0-6) 

**prior report checked:** Not determinable from available source; no NatSpec or README comment in indexed files documents this ordering as safe. [8](#0-7) 

**README/NatSpec checked:** `IPortalMigrator` NatSpec says `luanchToDEX` "may be delegate called from a payable function" — confirming an external call exists in the migration path. [9](#0-8) 

**unsupported assumption checked:** The attack requires the implementation contract to make an external call before updating status. This is unverified but not ruled out; the implementation is unindexed.

## Local Proof Required
**test type:** Foundry fork test (BSC mainnet fork at block 108382650) + unit test with mock migrator

**test file to add:** `test/SwapExactInputReentrancy.t.sol`

**test setup:**
1. Fork BSC at the live block; use proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`
2. Identify a live `Tradable` token with `circulatingSupply` near `dexSupplyThresh` (read from `_packedTokenStates` slot1)
3. Deploy a `MaliciousMigrator` that, when `luanchToDEX` is called, re-enters `swapExactInput` on Portal for the same token with a small BNB amount
4. If the migrator address is admin-settable, substitute it; otherwise use a mock that intercepts the ETH transfer or ERC-20 callback during migration
5. Alternatively: write a pure unit test against a local deployment where the implementation ordering can be instrumented

**expected assertion:**
- If reentrancy is possible: assert that the re-entrant `swapExactInput` call succeeds and the attacker receives tokens at bonding-curve price after migration is triggered → **HIGH_CONFIDENCE_CANDIDATE**
- If re-entrant call reverts with `TokenNotTradable` or `TokenAlreadyDEXed`: **REJECT** (status written before external call, CEI pattern holds)

**failure condition:** Re-entrant call succeeds and attacker balance of the token increases beyond what a single pre-migration buy would yield, while the DEX pool receives less liquidity than the full bonding-curve reserve.

### Citations

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

**File:** src/PortalBase.sol (L918-943)
```text
    /// @dev set the token status
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

**File:** src/interfaces/IPortal.sol (L1143-1144)
```text
    /// @notice error if token is not tradable
    error TokenNotTradable(address token);
```

**File:** src/interfaces/IPortal.sol (L1152-1154)
```text
    /// @notice error if the token has already been added to the DEX
    error TokenAlreadyDEXed(address token);

```

**File:** src/interfaces/IPortal.sol (L1847-1854)
```text
interface IPortalMigrator {
    /// @notice Add liquidity to DEX
    /// @param token The address of the token
    /// @dev This is an internal function
    ///      Any dispatch to this function should be checked in portal contract
    ///      This function may be dellegated called from a payable function.
    function luanchToDEX(address token) external payable;
}
```

**File:** src/PortalCommon.sol (L1-33)
```text
// SPDX-License-Identifier: MIT

pragma solidity ^0.8.13;

import {IPortalCommonTypes, IPortalTypes} from "./interfaces/IPortal.sol";
import {LibCurve} from "./libraries/Curve.sol";

/// @title  The Portal Common contract
/// @notice Stateless contract containing shared functions for curve, dex threshold, and fee calculations
contract PortalCommon is IPortalCommonTypes {
    //
    // Fee Related immutables
    //

    /// @dev Buy fee rate in basis points (bps), where 1% = 100 bps
    uint256 internal immutable FLAP_BUY_FEE;

    /// @dev Sell fee rate in basis points (bps), where 1% = 100 bps
    uint256 internal immutable FLAP_SELL_FEE;

    /// @dev Liquidity fee in basis points (0-10000, where 100 = 1%)
    uint256 internal immutable LIQUIDITY_FEE;

    /// @dev Reserve fee in basis points (0-10000, where 100 = 1%)
    uint256 internal immutable RESERVE_FEE;

    constructor(uint256 buyFeeRate_, uint256 sellFeeRate_, uint256 liquidityFee_, uint256 reserveFee_) {
        FLAP_BUY_FEE = buyFeeRate_;
        FLAP_SELL_FEE = sellFeeRate_;
        LIQUIDITY_FEE = liquidityFee_;
        RESERVE_FEE = reserveFee_;
    }

```
