import json
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

import click
import yaml
from rich import print

from .bitcoin import _rpc
from .k8s import delete_namespace, get_default_namespace, get_mission, get_pods
from .process import stream_command

WAR_MANIFESTS = files("manifests")
WARNET_NETWORK_DIR = files("networks")
NETWORK_DIR = Path("networks")
DEFAULT_NETWORK = Path("6_node_bitcoin")
NETWORK_FILE = "network.yaml"
DEFAULTS_FILE = "node-defaults.yaml"
HELM_COMMAND = "helm upgrade --install --create-namespace"
BITCOIN_CHART_LOCATION = str(files("charts").joinpath("bitcoincore"))
LND_CHART_LOCATION = str(files("charts").joinpath("lnd"))


@click.group(name="network")
def network():
    """Network commands"""


class Edge:
    def __init__(self, src: str, dst: str, data: dict[str, any]):
        self.src = src
        self.dst = dst
        self.data = data

    def to_dict(self):
        return {"src": self.src, "dst": self.dst, "data": self.data}


def edges_from_network_file(network_file: dict[str, any]) -> list[Edge]:
    edges = []
    for node in network_file["nodes"]:
        if "connect" in node:
            for connection in node["connect"]:
                edges.append(Edge(node["name"], connection, ""))
    return edges


def setup_logging_helm() -> bool:
    helm_commands = [
        "helm repo add grafana https://grafana.github.io/helm-charts",
        "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts",
        "helm repo update",
        f"helm upgrade --install --namespace warnet-logging --create-namespace --values {WAR_MANIFESTS}/loki_values.yaml loki grafana/loki --version 5.47.2",
        "helm upgrade --install --namespace warnet-logging promtail grafana/promtail",
        "helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --set grafana.enabled=false",
        f"helm upgrade --install --namespace warnet-logging loki-grafana grafana/grafana --values {WAR_MANIFESTS}/grafana_values.yaml",
    ]

    for command in helm_commands:
        if not stream_command(command):
            print(f"Failed to run Helm command: {command}")
            return False
    return True


def copy_network_defaults(directory: Path):
    """Create the project structure for a warnet project"""
    (directory / NETWORK_DIR / DEFAULT_NETWORK).mkdir(parents=True, exist_ok=True)
    target_network_defaults = directory / NETWORK_DIR / DEFAULT_NETWORK / DEFAULTS_FILE
    target_network_example = directory / NETWORK_DIR / DEFAULT_NETWORK / NETWORK_FILE
    shutil.copy2(WARNET_NETWORK_DIR / DEFAULT_NETWORK / DEFAULTS_FILE, target_network_defaults)
    shutil.copy2(WARNET_NETWORK_DIR / DEFAULT_NETWORK / NETWORK_FILE, target_network_example)


@network.command()
@click.argument(
    "network_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option("--logging/--no-logging", default=False)
def deploy(network_dir: Path, logging: bool):
    """Deploy a warnet with topology loaded from <network_dir>"""
    network_file_path = network_dir / NETWORK_FILE
    defaults_file_path = network_dir / DEFAULTS_FILE

    with network_file_path.open() as f:
        network_file = yaml.safe_load(f)

    namespace = get_default_namespace()

    for node in network_file["nodes"]:
        print(f"Deploying node: {node.get('name')}")
        try:
            temp_override_file_path = ""
            extra_conf_file_path = ""
            node_name = node.get("name")
            # all the keys apart from name and lnd
            node_config_override = {k: v for k, v in node.items() if k != "name" and k != "lnd"}

            cmd = f"{HELM_COMMAND} {node_name} {BITCOIN_CHART_LOCATION} --namespace {namespace} -f {defaults_file_path}"

            if node_config_override:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as temp_file:
                    yaml.dump(node_config_override, temp_file)
                    temp_override_file_path = Path(temp_file.name)
                cmd = f"{cmd} -f {temp_override_file_path}"

            if not stream_command(cmd):
                print(f"Failed to run Helm command: {cmd}")
                return

            lnd = node.get("lnd")
            if lnd:
                lnd_name = f"{node_name}-lnd"

                extra_conf = {
                    "config": ('\n').join([
                        f"bitcoind.rpchost={node_name}:18443",
                        f"bitcoind.zmqpubrawblock=tcp://{node_name}:28332",
                        f"bitcoind.zmqpubrawtx=tcp://{node_name}:28333",
                        f"alias={lnd_name}",
                        f"externalhosts={lnd_name}",
                        f"tlsextradomain={lnd_name}"
                    ])
                }

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as temp_file:
                    yaml.dump(extra_conf, temp_file)
                    extra_conf_file_path = Path(temp_file.name)

                cmd = f"{HELM_COMMAND} {lnd_name} {LND_CHART_LOCATION} --namespace {namespace} --set bitcoin_tank_name={node_name},lnd_name={lnd_name} -f {extra_conf_file_path}"
                if not stream_command(cmd):
                    print(f"Failed to run Helm command: {cmd}")
                    return

        except Exception as e:
            print(f"Error: {e}")
            return
        finally:
            if temp_override_file_path:
                Path(temp_override_file_path).unlink()
            if extra_conf_file_path:
                Path(extra_conf_file_path).unlink()


@network.command()
def down():
    """Bring down a running warnet"""
    if delete_namespace("warnet-logging"):
        print("Warnet logging deleted")
    else:
        print("Warnet logging NOT deleted")
    tanks = get_mission("tank")
    tanks.extend(get_mission("lightning"))
    for tank in tanks:
        cmd = f"helm uninstall {tank.metadata.name}"
        stream_command(cmd)
    # Clean up scenarios and other pods
    # TODO: scenarios should be helm-ified as well
    pods = get_pods()
    for pod in pods.items:
        cmd = f"kubectl delete pod {pod.metadata.name}"
        stream_command(cmd)


@network.command()
def connected():
    """Determine if all p2p connections defined in graph are established"""
    print(_connected())


def _connected():
    tanks = get_mission("tank")
    for tank in tanks:
        # Get actual
        peerinfo = json.loads(_rpc(tank.metadata.name, "getpeerinfo", ""))
        manuals = 0
        for peer in peerinfo:
            if peer["connection_type"] == "manual":
                manuals += 1
        # Even if more edges are specifed, bitcoind only allows
        # 8 manual outbound connections
        expected = tank.metadata.annotations["init_peers"]
        print(f"{tank.metadata.name} connections: expected={expected} actual={manuals}")
        if min(8, int(expected)) > manuals:
            print("Network not connected")
            return False
    print("Network connected")
    return True


@network.command()
def status():
    """Return pod status"""
    # TODO: make it a pretty table
    print(_status())


def _status():
    tanks = get_mission("tank")
    stats = []
    for tank in tanks:
        status = {
            "tank": tank.metadata.name,
            "bitcoin_status": tank.status.phase.lower(),
        }
        stats.append(status)
    return stats
