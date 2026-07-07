<!-- deepwiki_source_url: https://deepwiki.com/search/-deepwiki-candidate-triage-pro_2c37e1b4-e497-4e61-9f61-2dda6f20612c?mode=deep -->
<!-- deepwiki_verdict: needs_local_proof -->

## Verdict
NEEDS_LOCAL_PROOF

## Paid Scope Match
reward_extraction

## Exact Code Path
file: `src/Portal.sol`
function: `claim(address)`
symbols/lines: lines 144–156 — `claim()` carries `onlyIfBitFlagsSet` but no reentrancy guard; body is a bare `_delegateToImpl(PORTAL_ROLLER)`.

file: `src/Portal.sol`
function: `receive()`
symbols/lines: line 48 — `receive() external payable {}` — empty, accepts ETH unconditionally.

file: `src/PortalBase.sol`
function: `_delegateToImpl(address)`
symbols/lines: lines 831–843 — raw `delegatecall` with no reentrancy lock set before or after. [1](#0-0) [2](#0-1) [3](#0-2) 

## Attacker Path
**preconditions:**
- Attacker is the current `_tokenBeneficiaries[token]` for some token whose `lpLocks[token]` is non-zero (i.e., a V4/PCS-Infinity LP lock exists with accumulated fees).
- Attacker controls a contract with a `receive()` that re-enters `claim(token)`.

**attacker-controlled inputs:**
- `token` address passed to `claim()`.

**call sequence:**
1. Attacker contract calls `Portal.claim(token)`.
2. Portal `_delegateToImpl(PORTAL_ROLLER)` — roller logic runs in Portal's storage context.
3. Roller calls the external locker (`PORTAL_V4_CL_LOCKER` or equivalent) to `collectFees`.
4. Locker transfers accumulated LP fees in ETH to Portal; `Portal.receive()` accepts silently.
5. Roller then transfers ETH to `_tokenBeneficiaries[token]` (attacker contract) **before** zeroing the claimable accounting (unverified — roller source absent).
6. Attacker's `receive()` fires and calls `Portal.claim(token)` again.
7. If roller re-reads `lpLocks` / fee state from storage and it has not yet been cleared, a second full payout is issued.
8. Repeat until Portal BNB balance is drained or gas runs out.

## Why Existing Checks Fail
**No reentrancy guard anywhere in Portal.sol or PortalBase.sol.** A full-codebase grep for `nonReentrant`, `ReentrancyGuard`, `_reentrancyGuard`, and `_status` returns zero matches in Portal source files — only hits are inside the OpenZeppelin library files themselves. [1](#0-0) 

The `onlyIfBitFlagsSet` modifier on `claim()` only checks a feature-enable bitmask; it provides no cross-call exclusion. [4](#0-3) 

`_delegateToImpl` is a raw assembly `delegatecall` with no lock slot written before or after the call. [3](#0-2) 

**Critical unknown:** The `PORTAL_ROLLER` implementation is **not present** in this repository. The source file inventory (`src/Portal.sol`, `src/PortalBase.sol`, `src/PortalCommon.sol`, interfaces, libraries) contains no roller implementation. Whether the roller zeroes the claimable amount or LP-lock fee accounting **before** transferring ETH to the beneficiary is the decisive question that cannot be answered from available source alone.

**Note on the described path:** `Portal.receive()` is empty — it cannot itself re-enter `claim`. The actual re-entry trigger is the roller's ETH transfer to the beneficiary (attacker contract), whose own `receive()` calls back into `claim`. The prompt's phrasing "Portal.receive() → claim again" is a misdescription of the path; the re-entry originates from the attacker's `receive()`, not Portal's.

## Rejection Checks
**expected behavior checked:** CEI (checks-effects-interactions) compliance in the roller is the expected protection; its absence would be a bug, not expected behavior. Cannot confirm either way without roller source.

**prior report checked:** No prior report found in repository (no SECURITY.md, audit reports, or known-issues files present in the indexed source).

**README/NatSpec checked:** No NatSpec on `claim()` in Portal.sol documents reentrancy safety or intentional single-claim-per-block semantics. [1](#0-0) 

**unsupported assumption checked:** The assumption that the roller sends ETH to the beneficiary before clearing state is **unverified** — this is the exact condition that requires local fork testing to confirm or refute.

## Local Proof Required
**test type:** Foundry fork test on BSC

**test file to add:** `test/ClaimReentrancy.t.sol`

**test setup:**
```solidity
// Fork BSC at block 108382650
// Portal proxy: 0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0
// 1. Find a token address T where lpLocks[T].locks[0] != 0
//    (query getLocks(T) or read storage slot 165 directly)
// 2. Deploy attacker contract:
//    - constructor sets itself as _tokenBeneficiaries[T] via setTokenBeneficiary
//      (only valid if attacker is current beneficiary or token creator — check access control)
//    - receive() calls Portal.claim(T) up to N times, tracking ETH received
// 3. Record Portal.balance before call
```

**call sequence:**
```
attackerContract.attack() →
  Portal.claim(T) [first entry] →
    roller.claim(T) [delegatecall] →
      locker.collectFees(T) →
        Portal.receive() [ETH arrives] →
      transfer ETH to attacker →
        attacker.receive() →
          Portal.claim(T) [re-entry] → ...
```

**expected assertion (if vulnerable):**
```solidity
uint256 balBefore = address(portal).balance;
attacker.attack();
uint256 balAfter = address(portal).balance;
uint256 legitimateFee = /* single collectFees amount */;
assertEq(balBefore - balAfter, legitimateFee, "drained more than one fee cycle");
// If this assertion FAILS, reentrancy is confirmed
```

**failure condition:** If `balBefore - balAfter > legitimateFee` (attacker received multiple fee payouts from a single LP-lock fee accumulation), the invariant is broken and the finding is confirmed. If the roller clears state before the ETH transfer, the re-entry will return 0 on the second call and the assertion passes — REJECT.

### Citations

**File:** src/Portal.sol (L47-48)
```text
    // receive function to receive ether
    receive() external payable {}
```

**File:** src/Portal.sol (L144-156)
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
```

**File:** src/PortalBase.sol (L683-701)
```text
    modifier onlyIfBitFlagsSet(uint256 mask) {
        if (!_checkBitFlags(mask)) revert FeatureDisabled();
        _;
    }

    /// @dev check bit flags
    /// If a bit is off, means the feature is disabled
    function _checkBitFlags(uint256 mask) internal view returns (bool) {
        // We only check the bits in the mask are set
        // And ignore the bits that are not in the mask
        //
        //  -  mask => with only checking bits set
        //  -  mask ^ bitFlags =>
        //          XOR: all checking bits should be unset, if
        //          they are set in the bitFlags.
        //  - _ & mask, ignore the bits that are not in the mask
        //
        return (mask ^ bitFlags) & mask == 0;
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
