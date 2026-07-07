<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_a1bc6a47-6e8c-4e7a-bb40-2bc89ac788ca?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
fund_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `swapExactInput`
symbols/lines: lines 174–185 (dispatch to `PORTAL_TRADE_V2`); `ExactInputParams.permitData` field defined in `src/interfaces/IPortal.sol` lines 1749–1760

## Attacker Path
**preconditions:**
- Victim has signed a valid ERC-2612 permit for the quote token with `spender = Portal proxy`, `owner = victim`, `value ≥ inputAmount`, valid nonce and deadline
- Attacker observes the victim's pending `swapExactInput` call in the mempool and extracts the raw `permitData` bytes

**attacker-controlled inputs:**
- `params.inputToken` = quote token address (same as victim's permit)
- `params.outputToken` = any valid bonding-curve token
- `params.inputAmount` = value covered by victim's permit
- `params.permitData` = victim's captured permit bytes (owner=victim, spender=Portal, value, deadline, v, r, s)
- `msg.sender` = attacker

**call sequence:**
1. Attacker calls `Portal.swapExactInput(params)` with victim's `permitData`
2. Portal dispatches via `_delegateToImpl(PORTAL_TRADE_V2)` [1](#0-0) 
3. `PORTAL_TRADE_V2` implementation decodes `permitData`, calls `quoteToken.permit(victim, portal, value, deadline, v, r, s)` — sets `allowance[victim][portal] = value`
4. Implementation calls `quoteToken.transferFrom(victim, portal, inputAmount)` — pulls from victim
5. Portal buys bonding-curve tokens and sends output to `msg.sender` (attacker)

## Why Existing Checks Fail
The `swapExactInput` entry point in `Portal.sol` applies only the `onlyIfBitFlagsSet(CB_BIT_MASK_GLOBAL_SWITCH)` guard and then blindly delegates the full calldata (including `permitData`) to `PORTAL_TRADE_V2`. [2](#0-1) 

There is no check in `Portal.sol` or `PortalBase.sol` that binds the permit's `owner` field to `msg.sender` before the delegatecall. The `ExactInputParams` struct carries `permitData` as an opaque `bytes` field with no caller-binding validation at the dispatch layer. [3](#0-2) 

The `_delegateToImpl` function copies the entire calldata verbatim into the delegatecall, so whatever `permitData` the attacker supplies is forwarded unchanged. [4](#0-3) 

**Critical gap:** The `PORTAL_TRADE_V2` facet implementation — the only place where `permitData` is actually decoded and `permit(...)` is called — is **not present in the indexed source files**. Only `Portal.sol`, `PortalBase.sol`, and `PortalCommon.sol` are available. The `permitData` field appears exclusively in interface/struct definitions with no implementation logic visible. [5](#0-4) 

Whether the implementation correctly requires `permit.owner == msg.sender` before using the permit, or whether it uses the permit `owner` as the fund source while routing output tokens to `msg.sender`, cannot be determined from the indexed code alone. The attack is valid only if the implementation uses the permit `owner` as the `transferFrom` source while crediting output to `msg.sender`.

## Rejection Checks
**expected behavior checked:** Standard ERC-2612 permit is designed so `msg.sender` is the owner (see OpenZeppelin NatSpec: "msg.sender is used as the owner, leaving no ambiguity as to the signer intent"). [6](#0-5)  If `PORTAL_TRADE_V2` follows this pattern and requires `permit.owner == msg.sender`, the attack fails. This is the key unknown.

**prior report checked:** Not determinable from indexed source.

**README/NatSpec checked:** `ExactInputParams.permitData` is documented only as "Optional permit data for the input token (can be empty)" — no caller-binding guarantee stated. [5](#0-4) 

**unsupported assumption checked:** The attack requires the implementation to use `permit.owner` (victim) as the `transferFrom` source rather than `msg.sender`. This is the unverifiable assumption without `PORTAL_TRADE_V2` source.

## Local Proof Required
**test type:** Foundry fork test on BSC mainnet (block 108382650)

**test file to add:** `test/PermitReplayAttack.t.sol`

**test setup:**
1. Fork BSC at block 108382650, target proxy `0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0`
2. Select a live ERC-20 quote token with EIP-2612 permit support configured in Portal
3. Fund victim with quote tokens; generate a valid permit signature (`owner=victim, spender=Portal, value=X, nonce=current, deadline=future`)
4. Do NOT submit victim's `swapExactInput` — only capture the permit bytes

**expected assertion:**
```solidity
uint256 victimBalBefore = quoteToken.balanceOf(victim);
uint256 attackerTokensBefore = launchToken.balanceOf(attacker);

vm.prank(attacker);
portal.swapExactInput(ExactInputParams({
    inputToken: quoteToken,
    outputToken: launchToken,
    inputAmount: X,
    minOutputAmount: 0,
    permitData: victimPermitData  // victim's signature
}));

assertLt(quoteToken.balanceOf(victim), victimBalBefore);   // victim lost quote tokens
assertGt(launchToken.balanceOf(attacker), attackerTokensBefore); // attacker gained tokens
```

**failure condition:** If the implementation enforces `permit.owner == msg.sender` (or uses `msg.sender` as the `transferFrom` source regardless of permit owner), the call reverts or the victim's balance is unchanged → REJECT.

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

**File:** src/interfaces/IPortal.sol (L1749-1760)
```text
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

**File:** src/PortalBase.sol (L831-843)
```text
    function _delegateToImpl(address impl) internal {
        if (impl == address(0)) {
            revert FeatureDisabled();
        }
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }
```

**File:** lib/openzeppelin-contracts/contracts/token/ERC20/extensions/IERC20Permit.sol (L35-37)
```text
 * Observe that: 1) `msg.sender` is used as the owner, leaving no ambiguity as to the signer intent, and 2) the use of
 * `try/catch` allows the permit to fail and makes the code tolerant to frontrunning. (See also
 * {SafeERC20-safeTransferFrom}).
```
