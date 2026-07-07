<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_b77f1e06-a2aa-4453-9ae5-c960daaa58fc?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The attack conflates two independent issues and does not establish a concrete reward-extraction path. `collectV4Fees` being permissionless is expected design: it simply triggers fee collection and routes proceeds to `_tokenBeneficiaries[token]`, whoever that currently is. [1](#0-0)  The function carries no `onlyRole` or `onlyIfBitFlagsSet` guard, which is consistent with its documented "callable by anyone" intent — the output always flows to the registered beneficiary, not to `msg.sender`.

The attack therefore requires one of two preconditions:

1. **`setTokenBeneficiary` is permissionless** (anyone can redirect the beneficiary to themselves). If true, *that* would be the root vulnerability — an unauthorized beneficiary-change bug — not a `collectV4Fees` bug. The `PORTAL_ROLLER` source that implements `setTokenBeneficiary` is not present in the indexed repository files, so this cannot be confirmed or denied from source alone. [2](#0-1) 

2. **The attacker is already the legitimate beneficiary.** In that case, calling `collectV4Fees` to receive LP fees is *expected protocol behavior*, not a vulnerability. [3](#0-2) 

The "front-run a beneficiary change" framing also does not produce attacker profit: if the current beneficiary initiates `setTokenBeneficiary(token, newAddr)` and the attacker front-runs with `collectV4Fees`, the fees flow to the *current* beneficiary (the legitimate one), not to the attacker. The attacker gains nothing from that ordering.

Because the only path to attacker profit requires `setTokenBeneficiary` to be permissionless — an assumption that cannot be verified from the available source — and because `collectV4Fees` routing to the registered beneficiary is documented expected behavior, this candidate does not meet the bar for NEEDS_LOCAL_PROOF. The `collectV4Fees` function itself contains no broken invariant; any real bug lives in `setTokenBeneficiary` access control, which is a separate, unconfirmed claim.

### Citations

**File:** src/Portal.sol (L351-360)
```text
    function setTokenBeneficiary(
        address,
        /*token*/
        address /* newBeneficiary */
    )
        external
        override
    {
        _delegateToImpl(PORTAL_ROLLER);
    }
```

**File:** src/Portal.sol (L776-783)
```text
    function collectV4Fees(
        address /* token */
    )
        external
        override
    {
        _delegateToImpl(PORTAL_V4_CL_LOCKER);
    }
```

**File:** src/PortalBase.sol (L409-410)
```text
    /// @dev mapping from token to beneficiary, slot: 169
    mapping(address => address) internal _tokenBeneficiaries;
```
