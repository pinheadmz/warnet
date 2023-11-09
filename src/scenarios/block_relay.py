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
        # Get addrs of different types from all nodes
        addrs = []
        for i in range(2, self.num_nodes):
            miner = ensure_miner(self.nodes[i])
            for t in TYPES:
                addr = miner.getnewaddress("", t)
                addrs.append(addr)
                self.log.info(f"Got address from node {i}: {addr}")
        self.log.info(f"Collected {len(addrs)} addrs from {self.num_nodes - 2} nodes")

        # Generate one block to latch out of IBD and start addr gossip
        self.log.info("Generating block #1 from node 2")
        self.nodes[2].generatetoaddress(1, addrs[0], invalid_call=False)

        # Connect to target nodes
        self.log.info("Encouraging outbound connections to target nodes")
        for i in range(2, self.num_nodes):
            self.nodes[i].addpeeraddress(self.nodes[0].rpchost, 18444)
            self.nodes[i].addpeeraddress(self.nodes[1].rpchost, 18444)

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
                    amounts[choice(addrs)] = "0.00001"
                node = randrange(2, self.num_nodes)
                self.log.info(f"Sending tx {n}/{txs} with {outputs} outputs from node {node}")
                try:
                    self.nodes[node].sendmany(amounts=amounts)
                except Exception as e:
                    self.log.info(f"Send tx failed: {e}")
            node = randrange(2, self.num_nodes)
            self.log.info(f"Generating block from node {node}")
            self.nodes[node].generatetoaddress(1, choice(addrs), invalid_call=False)




if __name__ == "__main__":
    BlockRelay().main()
