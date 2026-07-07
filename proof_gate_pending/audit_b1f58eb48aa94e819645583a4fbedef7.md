<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_8821ac83-95b3-4b23-9a76-8a303ade0751?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The `collectV4Fees → TaxProcessor → addV4LPLiquidity` call chain is the **explicitly documented intended design**, not a reentrancy attack surface. The `IV4Locker` NatSpec in `src/interfaces/IPortal.sol` states `addV4LPLiquidity` is *"Called by TaxProcessor to reinvest LP-share tax revenue"* and `collectV4Fees` *"fees always flow through Portal → TaxProcessor → distribution"* — the TaxProcessor callback into `addV4LPLiquidity` is the expected behavior, not an exploit path. [1](#0-0) 

Beyond that, the theory has two fatal structural flaws:

**1. Attacker does not control TaxProcessor.** An unprivileged caller can invoke `collectV4Fees` (permissionless keeper), but the TaxProcessor is a protocol-configured contract. The attacker cannot force the TaxProcessor to call `addV4LPLiquidity` with attacker-chosen parameters or at an attacker-chosen moment. The TaxProcessor's behavior is fixed by protocol configuration, not by the `collectV4Fees` caller. [2](#0-1) 

**2. The actual implementation is not in scope source.** Both `collectV4Fees` and `addV4LPLiquidity` in `Portal.sol` are thin stubs that `_delegateToImpl(PORTAL_V4_CL_LOCKER)` — the entire accounting logic, reentrancy guards, and fee-tracking state live in the external `PORTAL_V4_CL_LOCKER` implementation contract, which is not present in the indexed source files. The theory's core claim (no reentrancy guard, double-counting accounting) cannot be verified or falsified from the available source. [3](#0-2) 

The claim that the TaxProcessor callback "double-counts" fees is an unverified assumption about the locker's internal accounting. Without the locker source, there is no source-level evidence that tokens are re-accounted rather than simply reinvested from already-transferred balances. The theory does not meet the minimum bar for NEEDS_LOCAL_PROOF because the attacker control precondition (controlling TaxProcessor behavior) is not satisfiable by an unprivileged caller.

### Citations

**File:** src/interfaces/IPortal.sol (L1817-1835)
```text
    /// @notice Collect V4/PCS Infinity LP fees for a token and distribute via TaxProcessor
    /// @dev Can be called by anyone (permissionless keeper). The Locker's collectAddress is
    ///      set to Portal, so fees always flow through Portal → TaxProcessor → distribution.
    /// @param token The token whose LP fees to collect
    function collectV4Fees(address token) external;

    /// @notice Add liquidity to locked V4/PCS Infinity LP positions for a token.
    /// @dev Called by TaxProcessor to reinvest LP-share tax revenue.
    ///      Tokens must be transferred to Portal before calling this function.
    ///      Portal (as lock owner) calls increaseLiquidity on the GoPlus/UNCX locker
    ///      for both the quote-only (lower) and token-only (upper) positions.
    /// @param token        The protocol token address
    /// @param tokenAmount  Amount of protocol token available for LP
    /// @param quoteAmount  Amount of quote token available for LP
    /// @return actualTokenUsed Total protocol token consumed
    /// @return actualQuoteUsed Total quote token consumed
    function addV4LPLiquidity(address token, uint256 tokenAmount, uint256 quoteAmount)
        external
        returns (uint256 actualTokenUsed, uint256 actualQuoteUsed);
```

**File:** src/Portal.sol (L776-788)
```text
    function collectV4Fees(
        address /* token */
    )
        external
        override
    {
        _delegateToImpl(PORTAL_V4_CL_LOCKER);
    }

    /// @inheritdoc IV4Locker
    function addV4LPLiquidity(address, uint256, uint256) external override returns (uint256, uint256) {
        _delegateToImpl(PORTAL_V4_CL_LOCKER);
    }
```
