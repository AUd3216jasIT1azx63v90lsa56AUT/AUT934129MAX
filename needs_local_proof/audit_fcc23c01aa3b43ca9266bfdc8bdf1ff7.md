<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_2ba884d4-16ce-4fb6-9cc9-0f5b4c5bc071?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
protocol_value_drain

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput`
symbols/lines: lines 174–185 (dispatcher); actual buy logic in `PORTAL_TRADE_V2` facet (not present in indexed source)

The dispatcher in Portal.sol simply routes to `PORTAL_TRADE_V2` via `_delegateToImpl`: [1](#0-0) 

`_getSwapImplementation` returns `PORTAL_TRADE_V2` for bonding-curve tokens: [2](#0-1) 

The reserve is stored in `_packedTokenStates` slot1 and written only via `_setTokenReserve`: [3](#0-2) 

## Attacker Path
**preconditions:** Any `Tradable`-status token with `quoteToken = NATIVE_GAS_TOKEN`; attacker is an unprivileged caller.

**attacker-controlled inputs:**
- `params.inputToken = address(0)` (native buy)
- `params.outputToken = <target token>`
- `params.inputAmount = X`
- `msg.value = Y` where `Y >> X`

**call sequence:**
1. Attacker calls `swapExactInput({inputToken: address(0), outputToken: token, inputAmount: X, minOutputAmount: 0, permitData: ""})` with `msg.value = Y`
2. Portal dispatches via `delegatecall` to `PORTAL_TRADE_V2`
3. If implementation uses `params.inputAmount` for curve math but writes `msg.value` (or `msg.value - fee`) to the reserve, the reserve grows by `Y` while tokens equivalent to only `X` are minted
4. Subsequent buyers pay inflated prices; attacker can sell previously-held tokens at the inflated price

## Why Existing Checks Fail
The Portal.sol dispatcher has no `msg.value == params.inputAmount` guard before delegating. The `onlyIfBitFlagsSet` modifier only checks the global halt flag. All accounting logic — including which value is used for the curve calculation and which is written to `_setTokenReserve` — lives entirely inside `PORTAL_TRADE_V2`, which is **not present in the indexed source files** of this repository. The hypothesis cannot be confirmed or refuted from available source alone.

The NatSpec for `buyOnCreation` explicitly documents that excess `msg.value` over `inputAmount` is kept as a fee (not refunded): [4](#0-3) 

Whether `swapExactInput` has the same behavior, or whether the excess is silently credited to the reserve rather than to a fee receiver, requires reading the `PORTAL_TRADE_V2` implementation.

## Rejection Checks
**expected behavior checked:** The `buyOnCreation` NatSpec documents excess `msg.value` as a fee, not a reserve credit — but this is a different function. No equivalent NatSpec exists for `swapExactInput` native buys.

**prior report checked:** No prior report found in indexed files.

**README/NatSpec checked:** `IPortalTradeV2.swapExactInput` NatSpec does not address `msg.value > inputAmount` behavior for native buys.

**unsupported assumption checked:** The core assumption — that `PORTAL_TRADE_V2` uses `inputAmount` for curve math but `msg.value` for reserve update — is unverified. The implementation could equally use `msg.value` for both (no bug), `inputAmount` for both with excess kept as fee (no reserve inflation), or the split described (bug). This is the key unknown.

## Local Proof Required
**test type:** Foundry fork test against BSC mainnet (block 108382650)

**test file to add:** `test/SwapExactInputMsgValueFork.t.sol`

**test setup:**
1. Fork BSC at block 108382650; target proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`
2. Select a live `Tradable` token with `quoteToken = NATIVE_GAS_TOKEN` (derive from recent `TokenBought` events)
3. Record `reserveBefore = getTokenState(token).reserve`
4. Call `swapExactInput({inputToken: address(0), outputToken: token, inputAmount: 1 ether, minOutputAmount: 0, permitData: ""})` with `msg.value = 2 ether`
5. Record `reserveAfter = getTokenState(token).reserve`

**expected assertion (no bug):**
```
assertApproxEqAbs(reserveAfter - reserveBefore, 1 ether * (10000 - fee) / 10000, tolerance);
// reserve grows by inputAmount minus fee, NOT by msg.value
```

**failure condition (bug confirmed):**
```
reserveAfter - reserveBefore ≈ 2 ether * (10000 - fee) / 10000
// reserve grew by msg.value, not inputAmount
```

If the reserve grows by `msg.value` while tokens minted correspond to `inputAmount`, the invariant is broken and the finding is a valid bonding-curve price manipulation. If the reserve grows by `inputAmount` (and excess `msg.value` goes to fee receiver or reverts), REJECT.

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

**File:** src/PortalBase.sol (L946-975)
```text
    function _setTokenReserve(address token, uint128 reserve) internal {
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
            packed = (packed & ~(uint256(type(uint96).max) << 56)) | (uint256(uint96(reserve)) << 56);
            assembly ("memory-safe") {
                sstore(slot, packed)
            }
        } else {
            uint256 slot1 = slot + 1;
            uint256 slot1val;
            assembly ("memory-safe") {
                slot1val := sload(slot1)
            }
            slot1val = (slot1val & ~uint256(type(uint128).max)) | uint256(reserve);
            assembly ("memory-safe") {
                sstore(slot1, slot1val)
            }
        }
    }
```

**File:** src/interfaces/IPortal.sol (L1681-1691)
```text
    ///
    /// @dev  This function is mainly for internal use (be delegated called from the portal contract)
    ///       The msg.value can be greater than inputAmount, the excess ETH will not be
    ///       refunded to the caller. They will be charged as a fee.
    ///
    ///       Note: the slippage is not checked in this function.
    ///
    function buyOnCreation(address token, address recipient, uint256 inputAmount)
        external
        payable
        returns (uint256 amount);
```
