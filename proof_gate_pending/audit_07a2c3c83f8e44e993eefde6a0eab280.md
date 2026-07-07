<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_702e4488-f23c-456b-92b7-0fbb54109735?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
REJECT

## Rejection Reason

The actual `swapExactInput` implementation that processes `permitData` lives in the `PORTAL_TRADE_V2` facet, which is not present in the indexed source files. The `Portal.sol` dispatcher simply calls `_delegateToImpl(implementation)` and the `permitData` field is only defined in the interface struct — zero permit-processing logic exists in any of the three indexed implementation files (`Portal.sol`, `PortalBase.sol`, `PortalCommon.sol`). [1](#0-0) 

The `permitData` bytes field appears exclusively in `src/interfaces/IPortal.sol` (struct definitions only) and not in any `.sol` implementation file. [2](#0-1) 

Without the `PORTAL_TRADE_V2` facet source, the critical question — whether the implementation decodes `owner` from `permitData` and calls `transferFrom(decodedOwner, ...)` (vulnerable) versus using `msg.sender` as the owner and `transferFrom(msg.sender, ...)` (safe, the OZ-recommended pattern) — cannot be answered from the indexed code. The OZ `IERC20Permit` security note present in the repo explicitly states that the safe pattern uses `msg.sender` as owner, which would make the described attack impossible regardless of permit replay. [3](#0-2) 

Promoting this to `NEEDS_LOCAL_PROOF` or higher requires source-level evidence from the actual facet implementation showing the vulnerable `transferFrom(decodedOwner, ...)` pattern. Absent that, the claim is speculative.

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

**File:** lib/openzeppelin-contracts/contracts/token/ERC20/extensions/IERC20Permit.sol (L19-36)
```text
 * built-in replay protection and can be submitted by anyone, they can be frontrun. A protocol that uses permits should
 * take this into consideration and allow a `permit` call to fail. Combining these two aspects, a pattern that may be
 * generally recommended is:
 *
 * ```solidity
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
```
