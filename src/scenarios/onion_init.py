#!/usr/bin/env python3

from time import sleep

from scenarios.utils import ensure_miner
from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Connect tanks over internal Tor network"


class OnionInit(WarnetTestFramework):
    def set_test_params(self):
        self.num_nodes = 12

    def add_options(self, parser):
        parser.add_argument(
            "--justsend",
            dest="justsend",
            action="store_true",
            help="Skip all setup and just send a raw transaction",
        )

    def run_test(self):
        if not self.options.justsend:
            self.log.info("Waiting for Tor DA health...")
            self.wait_until(lambda: self.warnet.container_interface.tor_ready(), timeout=600)

            self.log.info("Adding onion addresses to test node")
            for tank in self.warnet.tanks:
                info = self.nodes[tank.index].getnetworkinfo()
                for addr in info["localaddresses"]:
                    if "onion" in addr["address"]:
                        dst = tank.index
                        src = 0
                        self.log.info(f"addpeeraddress to tank {src}: tank {dst} @ {addr['address']}:{addr['port']}")
                        self.nodes[src].addpeeraddress(addr['address'], addr['port'])
                        continue

            self.log.info("Waiting for clearnet network connections...")
            self.wait_until(lambda: self.warnet.network_connected(), timeout=600)

            self.log.info("Generate initial blocks")
            miner = ensure_miner(self.nodes[1])
            m_addr = miner.getnewaddress()
            self.generatetoaddress(self.nodes[1], 200, m_addr)

            self.log.info("Waiting for blocks to propagate...")
            self.wait_until(lambda: self.nodes[0].getblockcount() == 200, timeout=600)

        wallet = ensure_miner(self.nodes[0])

        if not self.options.justsend:
            self.log.info("Funding test node")
            w_addr = wallet.getnewaddress()
            miner.sendtoaddress(w_addr, 100)
            self.generatetoaddress(self.nodes[1], 1, m_addr)
            self.wait_until(lambda: wallet.getbalance() > 0, timeout=600)

        self.log.info("Sending raw transaction...")
        raw = wallet.send(outputs={"bcrt1qjqmxmkpmxt80xz4y3746zgt0q3u3ferr34acd5":0.1}, add_to_wallet=False, minconf=0)
        self.log.info(raw)
        self.nodes[0].sendrawtransaction(raw["hex"])


if __name__ == "__main__":
    OnionInit().main()
