<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_0d11275c-872d-4436-88a0-9c3ed3bd723c?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The actual bonding-curve buy logic for `TOKEN_TAXED` / `TOKEN_TAXED_V2` tokens is not present in the indexed source. `Portal.sol`'s `swapExactInput` is a pure dispatcher that `delegatecall`s to `PORTAL_TRADE_V2` [1](#0-0)  — the facet that contains the tax-on-bonding-curve accounting. That facet contract is not among the verified source files (`src/Portal.sol`, `src/PortalBase.sol`, `src/PortalCommon.sol`, `src/libraries/Curve.sol`, and the interface/library files). [2](#0-1) 

The specific claim — that `taxAmount` is subtracted from `inputAmount` before the curve call but the full `msg.value` is added to `state.reserve` — is a concrete code-level assertion about lines that do not appear in any indexed file. `PortalBase.sol` exposes `_setTokenReserve` as a low-level setter [3](#0-2)  but contains no buy/tax logic; `PortalCommon.sol` contains only fee-rate helpers and curve-type lookups. [4](#0-3)  Without the `PORTAL_TRADE_V2` facet source, the reserve-update sequence cannot be read, so the accounting mismatch is unverifiable speculation rather than a source-level finding. Promoting an unverifiable theory to `NEEDS_LOCAL_PROOF` or higher would violate the "prefer REJECT over speculative reports" rule.

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

**File:** src/PortalCommon.sol (L127-157)
```text
    /// @dev Get buy fee based on fee profile
    /// @param profile The fee profile to use
    /// @return The buy fee in basis points (bps), where 1% = 100 bps
    function _buyFeeByProfile(FlapFeeProfile profile) internal view returns (uint256) {
        if (profile == FlapFeeProfile.FEE_GLOBAL_DEFAULT) {
            return FLAP_BUY_FEE;
        } else if (profile == FlapFeeProfile.FEE_FLAPSALE_V0) {
            return 100; // 1%
        } else if (profile == FlapFeeProfile.FEE_ZERO) {
            return 0; // 0% - no protocol fee
        } else {
            // Unknown profile, default to FEE_GLOBAL_DEFAULT
            return FLAP_BUY_FEE;
        }
    }

    /// @dev Get sell fee based on fee profile
    /// @param profile The fee profile to use
    /// @return The sell fee in basis points (bps), where 1% = 100 bps
    function _sellFeeByProfile(FlapFeeProfile profile) internal view returns (uint256) {
        if (profile == FlapFeeProfile.FEE_GLOBAL_DEFAULT) {
            return FLAP_SELL_FEE;
        } else if (profile == FlapFeeProfile.FEE_FLAPSALE_V0) {
            return 100; // 1%
        } else if (profile == FlapFeeProfile.FEE_ZERO) {
            return 0; // 0% - no protocol fee
        } else {
            // Unknown profile, default to FEE_GLOBAL_DEFAULT
            return FLAP_SELL_FEE;
        }
    }
```
