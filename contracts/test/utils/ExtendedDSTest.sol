// SPDX-License-Identifier: MIT
pragma solidity ^0.8.12;

import "ds-test/test.sol";
import {Vm} from "forge-std/Vm.sol";

contract ExtendedDSTest is DSTest {
     
    Vm public constant VM = Vm(HEVM_ADDRESS);
    
    // solhint-disable-next-line
    function assertNeq(address a, address b) internal {
        if (a == b) {
            emit log("Error: a != b not satisfied [address]");
            emit log_named_address("  Expected", b);
            emit log_named_address("    Actual", a);
            fail();
        }
    }

    // solhint-disable-next-line
    function assertApproxEq(uint a, uint b, uint margin_of_error) internal {
        if (a > b) {
            if (a - b > margin_of_error) {
                emit log("Error a not equal to b");
                emit log_named_uint("  Expected", b);
                emit log_named_uint("    Actual", a);
                fail();
            }
        } else {
            if (b - a > margin_of_error) {
                emit log("Error a not equal to b");
                emit log_named_uint("  Expected", b);
                emit log_named_uint("    Actual", a);
                fail();
            }
        }
    }
    
    // solhint-disable-next-line
    function assertApproxEq(uint a, uint b, uint margin_of_error, string memory err) internal {
        if (a > b) {
            if (a - b > margin_of_error) {
                emit log_named_string("Error", err);
                emit log_named_uint("  Expected", b);
                emit log_named_uint("    Actual", a);
                fail();
            }
        } else {
            if (b - a > margin_of_error) {
                emit log_named_string("Error", err);
                emit log_named_uint("  Expected", b);
                emit log_named_uint("    Actual", a);
                fail();
            }
        }
    }
}
