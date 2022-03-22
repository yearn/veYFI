// SPDX-License-Identifier: MIT
pragma solidity ^0.8.12;
import "forge-std/console.sol";

import {TestFixture} from "./utils/TestFixture.sol";

contract VeTest is TestFixture {
    // setup is run on before each test
    function setUp() public override {
        // setup ve
        super.setUp();
    }

    function testSetupVeOK() public {
        console.log("address of ve", address(ve));
        console.log("address of YFI", address(yfi));
        assertTrue(address(0) != address(yfi));
        assertTrue(address(0) != address(ve));
    }

}