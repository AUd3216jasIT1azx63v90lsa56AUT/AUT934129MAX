<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_9b167e55-8bb5-46dc-bf6b-17e5f5746d04?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
fund_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput`
symbols/lines: lines 173–185 (dispatcher); actual buy logic in `PORTAL_TRADE_V2` delegatecall target (not present in indexed source files) [1](#0-0) 

The `swapExactInput` entry point in `Portal.sol` resolves the implementation via `_getSwapImplementation(params.inputToken, params.outputToken)` and immediately `delegatecall`s it. The nativeToQuoteSwap buy path — including the BNB→USDT router call and the subsequent `state.reserve` update — executes entirely inside the `PORTAL_TRADE_V2` facet, whose source is **not present** in the indexed files (`src/Portal.sol`, `src/PortalBase.sol`, `src/PortalCommon.sol`, `src/interfaces/`, `src/libraries/`). [2](#0-1) 

## Attacker Path
**preconditions:**
- A token exists on the bonding curve whose `quoteTokenAddress` is an ERC20 (e.g. USDT) and whose `nativeToQuoteSwapEnabled` is `true` (i.e. `QuoteTokenConfiguration.nativeToQuoteSwapType != SWAP_DISABLED`).
- The BNB/USDT pool used by `MULTI_DEX_ROUTER` has enough depth to accept the swap but will return fewer USDT than a naive `msg.value × spot_price` estimate (normal slippage).

**attacker-controlled inputs:**
- `params.inputToken = address(0)` (native BNB)
- `params.outputToken = <ERC20-quote token address>`
- `params.inputAmount = X BNB`
- `params.minOutputAmount = 0` (or any value below actual bonding-curve output)
- `msg.value = X BNB`

**call sequence:**
1. Attacker calls `Portal.swapExactInput{value: X}(params)`.
2. Portal dispatches to `PORTAL_TRADE_V2` via `delegatecall`.
3. `PORTAL_TRADE_V2` detects `inputToken == address(0)` and `quoteToken != address(0)` → enters nativeToQuoteSwap branch.
4. Calls `MULTI_DEX_ROUTER` to swap `X BNB → USDT`; router returns `actualUSDT < estimatedUSDT` due to slippage.
5. **Hypothesised bug:** `state.reserve` is incremented by `estimatedUSDT` (or a value derived from `msg.value`) rather than `actualUSDT`.
6. Attacker (or a colluding seller) later calls `swapExactInput` (sell path) against the inflated reserve and receives more USDT than was actually deposited. [3](#0-2) [4](#0-3) 

## Why Existing Checks Fail
The `ExactInputParams.minOutputAmount` field is a slippage guard on the **final bonding-curve token output**, not on the intermediate BNB→USDT conversion amount. If the implementation uses a pre-swap estimate (e.g. a quoter call result or `msg.value × rate`) to update `state.reserve` rather than the actual `amountOut` returned by `MULTI_DEX_ROUTER.exactInputSingle` / `swapExactTokensForTokens`, the reserve will be overstated by the slippage delta on every nativeToQuoteSwap buy. The `_setTokenReserve` helper in `PortalBase` writes whatever value it is given with no independent balance check. [5](#0-4) 

**Critical limitation:** The `PORTAL_TRADE_V2` source is not in the indexed repository. It is impossible to confirm from source alone whether the reserve update uses `actualUSDT` or an estimate. The hypothesis is structurally plausible but unverified.

## Rejection Checks
**expected behavior checked:** The `minOutputAmount` guard covers the bonding-curve token output, not the intermediate quote-token swap — so it does not protect the reserve invariant if the implementation uses a pre-swap estimate.

**prior report checked:** Not found in `SECURITY.md` or `RESEARCHER.md` (not accessible in indexed files).

**README/NatSpec checked:** `IPortalTradeV2` NatSpec documents the nativeToQuoteSwap scenario but does not specify whether `state.reserve` is updated with actual or estimated USDT. [6](#0-5) 

**unsupported assumption checked:** The theory does not require oracle manipulation, malicious token owner action, or admin compromise — only normal DEX slippage on a live BNB/USDT pool, which is always present.

## Local Proof Required
**test type:** BSC fork test (Foundry `--fork-url`)

**test file to add:** `test/NativeToQuoteSwapReserveInvariant.t.sol`

**test setup:**
1. Fork BSC at a recent block where the live proxy (`0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`) has a USDT-quote token with `nativeToQuoteSwapEnabled = true`.
2. Record `state.reserve` before the swap and Portal's USDT balance (`IERC20(USDT).balanceOf(portal)`).
3. Call `portal.swapExactInput{value: 1 ether}(ExactInputParams({inputToken: address(0), outputToken: <USDT-quote token>, inputAmount: 1 ether, minOutputAmount: 0, permitData: ""}))`.
4. Record `state.reserve` after and Portal's USDT balance after.

**expected assertion (if bug exists):**
```
assertGt(state.reserve_after - state.reserve_before,
         IERC20(USDT).balanceOf(portal_after) - IERC20(USDT).balanceOf(portal_before),
         "reserve overstated vs actual USDT received");
```

**failure condition (REJECT trigger):** If `state.reserve` delta equals the actual USDT delta (i.e. the implementation uses `actualUSDT` from the router return value), the invariant holds and this finding must be rejected.

### Citations

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

**File:** src/PortalBase.sol (L256-256)
```text
    address internal immutable PORTAL_TRADE_V2;
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

**File:** src/interfaces/IPortal.sol (L828-843)
```text
    /// @dev The configuration of the "native to quote" swap
    /// i.e How to swap ETH for the quote token when the quote token is not ETH
    enum NativeToQuoteSwapType {
        SWAP_DISABLED, // 0: disabled
        SWAP_VIA_V2_POOL, // 1: swap through v2 pool
        SWAP_VIA_V3_2500_POOL, // 2: swap through v3 2500 pool
        SWAP_VIA_V3_500_POOL, // 3: swap through v3 500 pool
        SWAP_VIA_V3_3000_POOL, // 4: swap through v3 3000 pool
        SWAP_VIA_V3_10000_POOL, // 5: swap through v3 10000 pool
        SWAP_VIA_MIXED_ROUTER // 6: multi-hop via PancakeSwap Infinity MixedQuoter + UniversalRouter (BSC only)
        //    used for tokens like uUSD that route BNB ↔ USDT(V3) ↔ uUSD(BinPool).
        //    The actual routing logic is bypassed in _shouldUseMixedRouter() before
        //    the enum is checked, so this value serves as a meaningful marker when
        //    calling setQuoteTokenConfiguration — any non-SWAP_DISABLED value would
        //    work, but this makes intent explicit.
    }
```

**File:** src/interfaces/IPortal.sol (L1748-1760)
```text
    /// @notice Parameters for swapping exact input amount for output token
    struct ExactInputParams {
        /// @notice The address of the input token (use address(0) for native asset)
        address inputToken;
        /// @notice The address of the output token (use address(0) for native asset)
        address outputToken;
        /// @notice The amount of input token to swap (in input token decimals)
        uint256 inputAmount;
        /// @notice The minimum amount of output token to receive
        uint256 minOutputAmount;
        /// @notice Optional permit data for the input token (can be empty)
        bytes permitData;
    }
```

**File:** src/interfaces/IPortal.sol (L1794-1799)
```text
    ///   If the token's reserve is another ERC20 token (eg. USD*, i.e, the quote token is an ERC20 token):
    ///      - BUY with USD*: input token is the USD* address, output token is the token address
    ///      - SELL for USD*: input token is the token address, output token is the USD* address
    ///      - BUY with BNB or ETH: input token is address(0), output token is the token address.
    ///        (Note: this requires an internal swap to convert BNB/ETH to USD*, nativeToQuoteSwap must be anabled for this quote token)
    /// Note: Currently, this method supports trading tokens that is either still on the bonding curve or already listed on DEX.
```
