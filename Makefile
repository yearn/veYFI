# include .env file and export its env vars
# (-include to ignore error if it does not exist)
-include .env

# deps
update:; forge update

# Build & test
build  :; forge build

test  :; forge test
trace  :; forge test -vvv
# local with fork
test-fork   :; forge test --fork-url ${ETH_RPC_URL}
trace-fork   :; forge test -vvv --fork-url ${ETH_RPC_URL}
clean  :; forge clean
snapshot :; forge snapshot