import click

from .process import run_command

@click.group(name="ln")
def ln():
    """Control running lightning nodes"""


@ln.command(context_settings={"ignore_unknown_options": True})
@click.argument("pod", type=str)
@click.argument("command", type=str, required=True)
def rpc(pod: str, command: str):
    """
    Call lightning cli rpc <command> on <ln pod name>
    """
    print(_rpc(pod, command))


def _rpc(pod: str, command: str):
    # TODO: when we add back cln we'll need to describe the pod,
    # get a label with implementation type and then adjust command
    cmd = f"kubectl exec {pod} -- lncli --network=regtest {command}"
    return run_command(cmd)


@ln.command(context_settings={"ignore_unknown_options": True})
@click.argument("pod", type=str)
def pubkey(pod: str,):
    """
    Get lightning node pub key from <ln pod name>
    """
    ## TODO: again here, cln will need a different command
    info = _rpc(pod, "getinfo")
    print(info["identity_pubkey"])
