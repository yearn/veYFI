Mainnet contract types (ABIs) used by `tests/functional/test_redemption.py::test_redeployment_oracle`.

ape-etherscan 0.6.x only speaks Etherscan's retired V1 API, so CI copies these into ape's
contract cache (`~/.ape/ethereum/mainnet/contract_types/`) instead of fetching them.
ABIs are from the verified sources (Blockscout, cross-checked against Sourcify):

- `0xa85461AF...` Curve CryptoSwap implementation behind the YFI/ETH pool `0xC26b89A6...` (EIP-1167 proxy)
- `0x0bc529c0...` YFI
- `0x2fBa208E...` previous Redemption deployment
