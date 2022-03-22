// SPDX-License-Identifier: MIT
pragma solidity ^0.8.12;
pragma abicoder v2;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Vm} from "forge-std/Vm.sol";

import {Token} from "../Token.sol";
import {ExtendedDSTest} from "./ExtendedDSTest.sol";
import {IVotingEscrow} from "../../interfaces/IVotingEscrow.sol";

// Artifact paths for deploying from the deps folder, assumes that the command is run from
// the project root.
string constant veArtifact = "foundry-artifacts/VotingEscrow.json";

// Base fixture
contract TestFixture is ExtendedDSTest, stdCheats {
    using SafeERC20 for IERC20;

    IVotingEscrow public ve;
    IERC20 public yfi;

    function setUp() public virtual {
        Token _yfi = new Token("YFI");
        yfi = IERC20(address(_yfi));
        depoloyVE(address(yfi));

        // add more labels to make your traces readable
        VM.label(address(yfi), "YFI");
        VM.label(address(ve), "VE");

        // do here additional setup
    }

    // Deploys VotingEscrow
    function depoloyVE(address _token) public returns (address) {
        address _ve = deployCode(
            veArtifact,
            abi.encode(_token,"veYFI","veYFI", "1.0.0")
        );
        ve = IVotingEscrow(_ve);

        return address(ve);
    }
}
