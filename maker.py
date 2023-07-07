from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import ContractCustomError, ContractLogicError

import json
import time
import sys
import os

constants = None
positions = None
abis = None

try:
    with open(os.path.abspath("contracts.json")) as contractsAbi:
        abis = json.load(contractsAbi)
    with open(os.path.abspath("config.json")) as configs:
        constants = json.load(configs)
    with open(os.path.abspath("sensitive.json")) as sensitive:
        positions = json.load(sensitive)
except:
    sys.exit("Error: config files not found! or formatted properly!")

web3 = Web3(Web3.HTTPProvider(constants["nodeProvider"]))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


try:
    addressUsdt = web3.to_checksum_address(constants["addressUsdt"])
    addressPGT = web3.to_checksum_address(constants["addressToken"])
    addressSwap = web3.to_checksum_address(constants["addressSwap"])
    pair_address = web3.to_checksum_address(constants["addressPair"])

    abiPGT = abis["abiToken"]
    abiSwap = abis["abiSwap"]

    user_address = web3.to_checksum_address(constants["addressUser"])
    private_key = constants["privateKey"]

    amount_in = web3.to_wei(constants["depositAmount"], "ether")

    already_bought = positions["bought"]
    from_block = positions["fromBlock"]
    amount_out = positions["amountOut"]
except:
    sys.exit("Error: A value in config file is missing")


pgt = web3.eth.contract(address=addressPGT, abi=abiPGT)
usdt = web3.eth.contract(address=addressUsdt, abi=abiPGT)
router = web3.eth.contract(address=addressSwap, abi=abiSwap)


def get_balances(address):
    pgt_balance = web3.from_wei(pgt.functions.balanceOf(address).call(), "ether")
    usdt_balance = web3.from_wei(usdt.functions.balanceOf(address).call(), "ether")
    bnb_balance = web3.from_wei(web3.eth.get_balance(address), "ether")
    return (pgt_balance, usdt_balance, bnb_balance)


while True:
    if not already_bought:
        try:
            buy_tx = router.functions.swapExactTokensForTokens(
                web3.to_wei(amount_in, "ether"),
                web3.to_wei(amount_out, "ether"),
                [addressUsdt, addressPGT],
                user_address,
                int(time.time()) + 200,
            ).build_transaction(
                {
                    "from": user_address,
                    "nonce": web3.eth.get_transaction_count(user_address),
                }
            )
        except (ContractCustomError, ContractLogicError):
            (pgt, usdt, bnb) = get_balances(user_address)
            sys.exit(
                f"Tx failed: Do you have balance in Token({pgt}), Usdt({usdt}), Bnb({bnb}) ? Are tokens approved?"
            )
        except:
            sys.exit("Error: Buy Tx Failed!")

        try:
            signed_tx = web3.eth.account.sign_transaction(
                buy_tx, private_key=private_key
            )
            (_, out) = router.functions.getAmountsOut(
                amount_in,
                [addressUsdt, addressPGT],
            ).call()
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            amount_out = out
        except:
            (_, _, bnb) = get_balances(user_address)
            sys.exit(
                f"Error: transaction failed, invalid privateKey or insufficient gas.Bnb({bnb})"
            )

        from_block = web3.eth.wait_for_transaction_receipt(tx_hash)
        with open(os.path.abspath("sensitive.json"), "w") as sensitiveBought:
            position = {
                "bought": True,
                "amountOut": amount_out,
                "fromBlock": json.dumps(from_block, default=str),
            }
            json.dump(position, sensitiveBought, indent=4)

        already_bought = True

        print(f"Tokens bought with tx hash {web3.to_hex(tx_hash)}")

    # latest_block = web3.eth.get_block("latest")  # change to block num of buy order

    transfer_topic = web3.keccak(text="Transfer(address,address,uint256)").hex()

    logs = web3.eth.get_logs(
        {
            "address": addressPGT,
            "fromBlock": from_block["blockNumber"],
            "topics": [transfer_topic],
        }
    )

    for log in logs:
        decoded_log = pgt.events.Transfer().process_log(log)
        if (
            decoded_log
            and web3.to_checksum_address(decoded_log["args"]["from"]) == pair_address
        ):
            if decoded_log["args"]["value"] >= web3.to_wei("10", "ether"):
                (_, out) = router.functions.getAmountsOut(
                    amount_in,
                    [addressUsdt, addressPGT],
                ).call()
                if amount_out > out:
                    print("UwU! Found valid buy!!! selling....")
                    pgt_balance = pgt.functions.balanceOf(user_address).call()
                    (_, amount_out) = router.functions.getAmountsOut(
                        pgt_balance,
                        [
                            addressPGT,
                            addressUsdt,
                        ],
                    ).call()
                    try:
                        sell_tx = router.functions.swapExactTokensForTokens(
                            pgt_balance,
                            int(amount_out * (1 - 0.5 / 100)),
                            [
                                addressPGT,
                                addressUsdt,
                            ],
                            user_address,
                            int(time.time()) + 300,
                        ).build_transaction(
                            {
                                "from": user_address,
                                "nonce": web3.eth.get_transaction_count(user_address),
                            }
                        )
                    except (ContractCustomError, ContractLogicError):
                        (pgt, usdt, bnb) = get_balances(user_address)
                        sys.exit(
                            f"Sell Tx failed: Do you have balance Token({pgt}), Usdt({usdt}), Bnb({bnb})? Are tokens approved?"
                        )

                    try:
                        signed_tx = web3.eth.account.sign_transaction(
                            sell_tx, private_key=private_key
                        )
                        tx_hash = web3.eth.send_raw_transaction(
                            signed_tx.rawTransaction
                        )
                    except:
                        (_, _, bnb) = get_balances(user_address)
                        sys.exit(
                            f"Error: transaction failed, invalid privateKey or insufficient gas.Bnb({bnb})"
                        )
                    with open(
                        os.path.abspath("sensitive.json"), "w"
                    ) as sensitiveBought:
                        position = {"bought": False, "amountOut": 0, "fromBlock": {}}
                        json.dump(position, sensitiveBought, indent=4)
                    already_bought = False
                    print(f"Sold with tx hash ({web3.to_hex(tx_hash)})!!!  OwO!")
                    break
                else:
                    print("OwO! Found buy but not profitable. Holding...")
            else:
                print("found buy less than 10 tokens, holding...")
        else:
            print("No buy found...")
    print("sleep 5 minuites")
    time.sleep(300)
