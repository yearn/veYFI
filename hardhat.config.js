
// See https://hardhat.org/config/ for config options.
module.exports = {
  solidity: "0.8.15",
  networks: {
    hardhat: {
      hardfork: "london",
      // Base fee of 0 allows use of 0 gas price when testing
      initialBaseFeePerGas: 0,
      accounts: {
        mnemonic: "test test test test test test test test test test test junk",
        path: "m/44'/60'/0'",
        count: 10
      }
    },
  },
};
