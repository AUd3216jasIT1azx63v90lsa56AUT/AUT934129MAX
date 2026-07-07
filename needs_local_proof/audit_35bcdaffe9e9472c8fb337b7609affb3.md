<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_b9fe073c-4514-4af3-ae45-88a3dc4fa1da?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The `_getSwapImplementation` else-branch does return `PORTAL_TRADE_V2` for `TokenStatus.Staged` (confirmed at `src/Portal.sol:73-74`), but the PORTAL_TRADE_V2 implementation is **not present in the repository source files** — it is an immutable delegatecall target set at construction time whose source is not indexed here. The developer comment at line 73 explicitly states `"will fail in implementation"`, asserting the status check exists inside PORTAL_TRADE_V2. Without that source, the claim that PORTAL_TRADE_V2 silently proceeds to trade a Staged token is an unsupported assumption. [1](#0-0) 

Beyond the missing source, the impact claim ("buy tokens at zero cost from an uninitialized reserve") is not credible on its own: a Staged token has `reserve = 0` and `circulatingSupply = 0` in `_packedTokenStates`, and bonding-curve math operating on those zero values would produce a division-by-zero or zero-output revert rather than a profitable trade. For V2+ token versions the token supply is pre-minted and held by Portal, but the curve arithmetic still requires a non-zero reserve to price a buy. [2](#0-1) 

Additionally, `stageNewTokenV5` is gated to `SALE_FORGE` only, so an unprivileged attacker cannot manufacture the Staged precondition themselves; they can only target tokens already staged by SALE_FORGE. [3](#0-2) 

The combination of (a) unverifiable PORTAL_TRADE_V2 status-check behavior, (b) developer assertion that it will revert, and (c) zero-reserve arithmetic making a profitable trade implausible means this does not meet the bar for NEEDS_LOCAL_PROOF. The hypothesis requires the PORTAL_TRADE_V2 source to be audited directly before any further triage.

### Citations

**File:** src/Portal.sol (L66-75)
```text
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
```

**File:** src/Portal.sol (L313-318)
```text
        // TODO: open to public after SaleForge Launch
        if (msg.sender != SALE_FORGE) {
            revert OnlySaleForge();
        }
        _delegateToImpl(PORTAL_LAUNCHER_TWO_STEP);
    }
```

**File:** src/PortalBase.sol (L79-83)
```text
        //
        uint128 reserve;
        // 128bit: the current reserve of the token
        uint128 circulatingSupply; // 128bit: the current circulating supply of the token
        //
```
