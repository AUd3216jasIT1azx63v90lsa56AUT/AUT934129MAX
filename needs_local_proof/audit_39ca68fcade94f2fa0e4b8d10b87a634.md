<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_b96c2005-26bc-4368-b344-0317926881ed?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

The actual `swapExactInput` implementation lives in `PORTAL_TRADE_V2` (a delegatecall facet), and the migration logic lives in the migrator contracts. Neither is present in this repository. However, there is a critical structural observation I can make from the available source.

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
fund_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput` → `_getSwapImplementation` → `_delegateToImpl(PORTAL_TRADE_V2)`
symbols/lines:

- `_getSwapImplementation` reads `state.status` at lines 63–75 to route to `PORTAL_TRADE_V2` (bonding curve) or `PORTAL_DEX_ROUTER` (DEX)
- `_setTokenStatus` writes `status` into packed storage at `PortalBase.sol:919–943`
- No `nonReentrant` modifier exists anywhere in `src/*.sol` — confirmed by grep returning zero matches in source files [1](#0-0) [2](#0-1) 

## Attacker Path
**preconditions:**
- A token is in `TokenStatus.Tradable` with `circulatingSupply` close to `dexSupplyThresh`
- The attacker controls a contract that can receive a callback during the migration path (e.g., via a native BNB `receive()` triggered by the migrator sending BNB, or via a token `transfer` hook if the token is a tax token)

**attacker-controlled inputs:**
- `ExactInputParams` with `inputToken` = quote token (BNB/ERC-20), `outputToken` = target bonding-curve token, `amountIn` = exactly the remaining amount to push `circulatingSupply >= dexSupplyThresh`

**call sequence:**
1. Attacker calls `swapExactInput` with the threshold-crossing amount
2. `_getSwapImplementation` reads `status == Tradable` → routes to `PORTAL_TRADE_V2`
3. `PORTAL_TRADE_V2` executes the buy, detects `circulatingSupply >= dexSupplyThresh`, triggers migration
4. Migration path calls `_setTokenStatus(DEX)` then calls external migrator (or vice versa — order unknown without `PORTAL_TRADE_V2` source)
5. **If status is still `Tradable` during the external migrator call**: attacker's contract re-enters `swapExactInput`
6. Re-entrant `_getSwapImplementation` reads `status == Tradable` → routes to `PORTAL_TRADE_V2` again
7. Attacker buys tokens at bonding-curve price after migration has been triggered but before the DEX pool is funded

## Why Existing Checks Fail
**No reentrancy guard:** The grep for `nonReentrant`, `ReentrancyGuard`, `_reentrancyGuard`, `_status`, `_locked` returns zero matches in `src/*.sol`. There is no `ReentrancyGuardUpgradeable` in the inheritance chain of `Portal`, `PortalBase`, or `PortalCommon`. [3](#0-2) 

**The only structural protection** is the status-routing in `_getSwapImplementation`: if `_setTokenStatus(DEX)` is called *before* the external migrator call, a reentrant `swapExactInput` is routed to `PORTAL_DEX_ROUTER` (which would fail on an unfunded pool). However, if the order is reversed — external migrator call first, then `_setTokenStatus(DEX)` — the status is still `Tradable` during the callback window and the bonding-curve path remains open. [4](#0-3) 

The actual order of `_setTokenStatus(DEX)` vs. the external migrator call is in `PORTAL_TRADE_V2` and the migrator contracts (`PORTAL_UNIV3_MIGRATOR`, `PORTAL_UNIV2_MIGRATOR`, `PORTAL_UNI_V4_MIGRATOR`, `PORTAL_PCS_INFINITY_CL_MIGRATOR`), none of which are present in this repository. [5](#0-4) 

## Rejection Checks
**expected behavior checked:** Buying at bonding-curve price after migration is triggered is not expected behavior — the invariant is that no bonding-curve trades occur after the DEX transition begins. [6](#0-5) 

**prior report checked:** Not determinable from available source; no NatSpec or README in this repository documents this as a known issue.

**README/NatSpec checked:** No reentrancy protection is documented or annotated on `swapExactInput`. [7](#0-6) 

**unsupported assumption checked:** The reentrancy callback requires the migrator to make an external call back to an attacker-controlled address (e.g., BNB transfer to `msg.sender`, or a tax-token transfer hook). This is plausible for native-BNB quote tokens where the migrator sends BNB to the Portal proxy and the proxy's `receive()` is payable, but the exact callback surface depends on the migrator implementation not present here.

## Local Proof Required
**test type:** Foundry fork test (BSC mainnet fork at block 108382650) or unit test with mock migrator

**test file to add:** `test/ReentrancyMigration.t.sol`

**test setup:**
1. Deploy or fork Portal proxy at `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`
2. Create a token with a known `dexSupplyThresh` (use `DexThreshType._1_PERCENT` for a small threshold)
3. Buy tokens up to `dexSupplyThresh - epsilon`
4. Deploy a mock migrator that, when called, re-enters `swapExactInput` on Portal before returning
5. If the migrator is not replaceable on the live deployment, use a unit test with a mock Portal that exposes the internal `_launchToDEX` flow with a controllable migrator address

**expected assertion:**
- If vulnerable: the re-entrant `swapExactInput` succeeds and the attacker receives tokens at bonding-curve price after migration is triggered → assert `TokenBought` event emitted inside the re-entrant call
- If protected: the re-entrant call reverts (either `TokenNotTradable` or routed to `PORTAL_DEX_ROUTER` which fails on unfunded pool)

**failure condition:** If the re-entrant call succeeds and the attacker's token balance increases at bonding-curve price after the migration threshold is crossed, the invariant is broken and this is a confirmed fund-extraction finding. If it reverts in all tested migrator orderings, REJECT.

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

**File:** src/Portal.sol (L173-185)
```text
    /// @inheritdoc IPortalTradeV2
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

**File:** src/PortalBase.sol (L29-32)
```text
contract PortalBase is IPortalTypes, PortalCommon, AccessControlUpgradeable {
    using EnumerableSetUpgradeable for EnumerableSetUpgradeable.Bytes32Set;
    using SafeERC20 for IERC20;

```

**File:** src/PortalBase.sol (L243-248)
```text
    address internal immutable PORTAL_UNIV3_MIGRATOR;

    /// @dev TaxTokenMigrator: The address of the migrator contract
    /// This migrator contract is used to migrate the tax tokens from bonding curve to Uniswap V2 DEX
    address internal immutable PORTAL_UNIV2_MIGRATOR;

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

**File:** src/interfaces/IPortal.sol (L124-138)
```text
    /// @notice the status of a token
    /// The token has 5 statuses:
    //    - Tradable: The token can be traded(buy/sell)
    //    - InDuel: (obsolete) The token is in a battle, it can only be bought but not sold.
    //    - Killed: (obsolete) The token is killed, it can not be traded anymore. Can only be redeemed for another token.
    //    - DEX: The token has been added to the DEX
    //    - Staged: The token is staged but not yet created (address is predetermined)
    enum TokenStatus {
        Invalid, // The token does not exist
        Tradable,
        InDuel, // obsolete
        Killed, // obsolete
        DEX,
        Staged // The token is staged (address determined, but not yet created)
    }
```
