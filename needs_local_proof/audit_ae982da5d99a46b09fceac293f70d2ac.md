<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_6a0047f1-944f-4cfb-8f60-5b99f8e701e0?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The actual `swapExactInput` permit-handling logic lives in the `PORTAL_TRADE_V2` delegatecall facet, which is not present in the indexed source files (`src/Portal.sol`, `src/PortalBase.sol`, `src/PortalCommon.sol`). The entry point in `src/Portal.sol` only dispatches via `_delegateToImpl`: [1](#0-0) 

The `_delegateToImpl` target for swaps is the `PORTAL_TRADE_V2` immutable: [2](#0-1) 

Without the source of `PORTAL_TRADE_V2`, there is no source-level evidence that the permit call uses an attacker-supplied `owner` rather than hardcoding `msg.sender`. The OZ `IERC20Permit` documentation embedded in this repo explicitly recommends using `msg.sender` as the owner to prevent exactly this class of attack: [3](#0-2) 

The `_burnToken` helper in `PortalBase.sol` — the only `safeTransferFrom` call visible in the indexed source — passes `payer` (which is `msg.sender` in the sell path), not an attacker-supplied address: [4](#0-3) 

The entire attack premise (permit `owner` taken from attacker-supplied `permitData`, then `safeTransferFrom` pulling from that owner) is unverifiable from the available indexed source. Promoting this to `NEEDS_LOCAL_PROOF` or higher requires first locating and reading the `PORTAL_TRADE_V2` implementation source; without it, the claim is purely speculative and fails the source-level evidence gate.

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

**File:** src/PortalBase.sol (L255-257)
```text
    /// @dev The Token Trade V2 contract address
    address internal immutable PORTAL_TRADE_V2;

```

**File:** src/PortalBase.sol (L796-799)
```text
            // we don't need to do a self transfer in this case.
            if (payer != address(this)) {
                IERC20(token).safeTransferFrom(payer, address(this), amount);
            }
```

**File:** lib/openzeppelin-contracts/contracts/token/ERC20/extensions/IERC20Permit.sol (L24-37)
```text
 * function doThingWithPermit(..., uint256 value, uint256 deadline, uint8 v, bytes32 r, bytes32 s) public {
 *     try token.permit(msg.sender, address(this), value, deadline, v, r, s) {} catch {}
 *     doThing(..., value);
 * }
 *
 * function doThing(..., uint256 value) public {
 *     token.safeTransferFrom(msg.sender, address(this), value);
 *     ...
 * }
 * ```
 *
 * Observe that: 1) `msg.sender` is used as the owner, leaving no ambiguity as to the signer intent, and 2) the use of
 * `try/catch` allows the permit to fail and makes the code tolerant to frontrunning. (See also
 * {SafeERC20-safeTransferFrom}).
```
