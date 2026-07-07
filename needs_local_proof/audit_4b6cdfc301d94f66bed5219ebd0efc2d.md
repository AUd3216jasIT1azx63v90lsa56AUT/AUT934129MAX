<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_9f4a7494-845d-4c8e-92f7-ea1231adae8f?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The PORTAL_ROLLER implementation — the only contract that contains the actual `claim` and `delegateClaim` logic — is not present in this repository. The repository contains only the dispatch stubs in `src/Portal.sol` (lines 144–171) that forward via `_delegateToImpl(PORTAL_ROLLER)`, the storage layout in `src/PortalBase.sol`, stateless helpers in `src/PortalCommon.sol`, and interface/ABI files. [1](#0-0) 

`PORTAL_ROLLER` is an immutable address set at constructor time from `params.roller_` and is never defined or deployed within this source tree. [2](#0-1) 

Without the PORTAL_ROLLER source, it is impossible to:
- Confirm whether a reentrancy guard exists or is absent
- Verify the order of operations (whether LP fee state is reset before or after the BNB/token transfer to the beneficiary)
- Show that the locker's `collect` call creates a reentrant callback window
- Demonstrate that existing checks are insufficient

The entire reentrancy/double-claim theory rests on assumptions about the PORTAL_ROLLER internals that cannot be verified from the indexed code. Promoting this to NEEDS_LOCAL_PROOF or higher without source-level evidence from the actual implementation would be speculative, which the rules explicitly reject.

### Citations

**File:** src/Portal.sol (L144-171)
```text
    function claim(
        address /*token*/
    )
        external
        override
        onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)
        returns (
            uint256, /*tokenAmount*/
            uint256 /*ethAmount*/
        )
    {
        _delegateToImpl(PORTAL_ROLLER);
    }

    /// @inheritdoc IRoller
    function delegateClaim(
        address /*token*/
    )
        external
        override
        onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)
        returns (
            uint256, /*tokenAmount*/
            uint256 /*ethAmount*/
        )
    {
        _delegateToImpl(PORTAL_ROLLER);
    }
```

**File:** src/PortalBase.sol (L258-259)
```text
    /// @dev The Portal Roller Contract Address
    address internal immutable PORTAL_ROLLER;
```
