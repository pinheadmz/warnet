#!/usr/bin/env python3
from random import randrange, choice
from warnet.test_framework_bridge import WarnetTestFramework
from scenarios.utils import ensure_miner

TYPES = ["legacy", "p2sh-segwit", "bech32", "bech32m"]

def cli_help():
    return "Connect peers to two test nodes and simulate network activity"


class BlockRelay(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        # Create wallets
        for node in self.nodes:
            self.log.info(f"Creating wallet for node {node.index}")
            node.createwallet("miner", descriptors=True)

        # Connect to target nodes
        self.log.info("Encouraging outbound connections to target nodes")
        for i in range(2, self.num_nodes):
            try:
                self.nodes[i].addnode(self.nodes[0].rpchost, "add")
            except Exception as e:
                self.log.info(f"addnode 0 failed: {e}")
            try:
                self.nodes[i].addnode(self.nodes[1].rpchost, "add")
            except Exception as e:
                self.log.info(f"addnode 1 failed: {e}")

        # Generate enough blocks so each node has mature coinbase coins
        miners = self.num_nodes - 2
        blocks = miners + 110
        for i in range(blocks):
            node = (i % (self.num_nodes - 2)) + 2
            self.log.info(f"Generating block {i}/{blocks} from node {node}")
            addr = self.nodes[node].getnewaddress()
            self.nodes[node].generatetoaddress(1, addr, invalid_call=False)

        # Random transaction blizzard
        while True:
            txs = randrange(50, 300)
            for n in range(txs):
                amounts = {}
                outputs = randrange(10) + 1
                for _ in range(outputs):
                    node = choice(self.nodes)
                    addr = node.getnewaddress("", choice(TYPES))
                    amounts[addr] = "0.00001"
                    self.log.info(f" got addr from node {node.index}: {addr}")
                node = randrange(2, self.num_nodes)
                self.log.info(f"Sending tx {n}/{txs} with {outputs} outputs from node {node}")
                try:
                    self.nodes[node].sendmany(amounts=amounts)
                except Exception as e:
                    self.log.info(f"Send tx failed: {e}")
            node = randrange(2, self.num_nodes)
            self.log.info(f"Generating block from node {node}")
            self.nodes[node].generatetoaddress(1, addr, invalid_call=False)




if __name__ == "__main__":
    BlockRelay().main()
