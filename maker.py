from web3 import Web3
from web3.middleware import geth_poa_middleware

import json
import time

web3 = Web3(Web3.HTTPProvider(""))
web3.middleware_onion.inject(geth_poa_middleware,layer=0)


constants = None
with open("/workspace/AMMToken-Bot/contracts.json") as contracts:
    constants = json.load(contracts)

contractPGT = constants["addressPGT"]
contractSwap= constants["addressSwap"]
abiPGT = constants["abiPGT"]
abiSwap = constants["abiSwap"]

pgt = web3.eth.contract(address=contractPGT, abi=abiPGT)
router= web3.eth.contract(address=contractSwap,abi=abiSwap)

while True:
    latest_block= web3.eth.get_block('latest')#change to block num of buy order
    from_block=latest_block.number - 5000

    transfer_topic= web3.keccak(text="Transfer(address,address,uint256)").hex()

    logs= web3.eth.get_logs({
        'address':contractPGT,
        'fromBlock':from_block,#change to block num of buy order
        'topics':[transfer_topic]
    })

    for log in logs:
        decoded_log= pgt.events.Transfer().process_log(log)
        if decoded_log and decoded_log["args"]["from"]=="0xaCFe55620451089c49C1F2635CE10F141cBeb7eB":
            if decoded_log["args"]["value"]>= web3.to_wei("10","ether"):
                print("sold")
                break
            else:
                print("pass")
    time.sleep(40)
