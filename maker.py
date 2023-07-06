from web3 import Web3
from web3.middleware import geth_poa_middleware

import json
import time
import os

constants = None
abis = None

with open(os.path.abspath("contracts.json")) as contractsAbi:
    abis = json.load(contractsAbi)
with open(os.path.abspath("config.json")) as configs:
    constants = json.load(configs)

web3 = Web3(Web3.HTTPProvider(constants["nodeProvider"]))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

already_bought = False


usdt = constants["addressUsdt"]
addressPGT = constants["addressToken"]
addressSwap = constants["addressSwap"]
pair_address = constants["addressPair"]

abiPGT = abis["abiToken"]
abiSwap = abis["abiSwap"]

user_address = constants["addressUser"]
private_key = constants["privateKey"]

amount_in = 0
amount_out = 0

pgt = web3.eth.contract(address=addressPGT, abi=abiPGT)
router = web3.eth.contract(address=addressSwap, abi=abiSwap)

from_block = None

while True:
    if not already_bought:
        buy_tx = router.functions.swapExactTokensForTokens(
            web3.to_wei(amount_in, "ether"),
            web3.to_wei(amount_out, "ether"),
            [web3.to_checksum_address(usdt), web3.to_checksum_address(addressPGT)],
            web3.to_checksum_address(user_address),
            int(time.time()) + 200,
        ).build_transaction(
            {
                "from": user_address,
                "nonce": web3.eth.get_transaction_count(user_address),
            }
        )
        signed_tx = web3.eth.account.sign_transaction(buy_tx, private_key=private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        from_block = web3.eth.wait_for_transaction_receipt(tx_hash)
        already_bought = True

        block_hash = web3.eth.get_block(from_block.block_number).hash
        print(f"Tokens bought with tx hash {block_hash.hex()}")

    # latest_block = web3.eth.get_block("latest")  # change to block num of buy order

    transfer_topic = web3.keccak(text="Transfer(address,address,uint256)").hex()

    logs = web3.eth.get_logs(
        {
            "address": addressPGT,
            "fromBlock": from_block.block_number,  # change to block num of buy order
            "topics": [transfer_topic],
        }
    )

    for log in logs:
        decoded_log = pgt.events.Transfer().process_log(log)
        if decoded_log and decoded_log["args"]["from"] == pair_address:
            if decoded_log["args"]["value"] >= web3.to_wei("10", "ether"):
                print("Found valid buy!!! selling....")
                pgt_balance = pgt.functions.balanceOf(user_address).call()
                (_, amount_out) = router.functions.getAmountsOut(
                    pgt_balance,
                    [
                        web3.to_checksum_address(addressPGT),
                        web3.to_checksum_address(usdt),
                    ],
                ).call()
                sell_tx = router.functions.swapExactTokensForTokens(
                    pgt_balance,
                    amount_out,
                    [
                        web3.to_checksum_address(usdt),
                        web3.to_checksum_address(addressPGT),
                    ],
                    web3.to_checksum_address(user_address),
                    int(time.time()) + 200,
                ).build_transaction(
                    {
                        "from": user_address,
                        "nonce": web3.eth.get_transaction_count(user_address),
                    }
                )
                signed_tx = web3.eth.account.sign_transaction(
                    sell_tx, private_key=private_key
                )
                tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                tx_result = web3.eth.wait_for_transaction_receipt(tx_hash)
                already_bought = False
                break
            else:
                print("found buy less than 10 tokens")
    print("sleep 20 seconds")
    time.sleep(20)
