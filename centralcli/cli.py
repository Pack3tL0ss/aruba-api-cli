#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
import os
import sys
import importlib
from pathlib import Path
from typing import List

import typer

# Detect if called from pypi installed package or via cloned github repo (development)
try:
    from centralcli import clibatch, clicaas, clido, clishow, clidel, cliadd, cliupdate, cliupgrade, cliclone, cli, log
except (ImportError, ModuleNotFoundError) as e:
    pkg_dir = Path(__file__).absolute().parent
    if pkg_dir.name == "centralcli":
        sys.path.insert(0, str(pkg_dir.parent))
        from centralcli import clibatch, clicaas, clido, clishow, clidel, cliadd, cliupdate, cliupgrade, cliclone, cli, log
    else:
        print(pkg_dir.parts)
        raise e

from centralcli.central import CentralApi  # noqa
from centralcli.constants import RefreshWhat, IdenMetaVars, BounceArgs

iden = IdenMetaVars()

CONTEXT_SETTINGS = {
    # "token_normalize_func": lambda x: cli.normalize_tokens(x),
    "help_option_names": ["?", "--help"]
}

app = typer.Typer(context_settings=CONTEXT_SETTINGS)
app.add_typer(clishow.app, name="show",)
app.add_typer(clido.app, name="do",)
app.add_typer(clidel.app, name="delete")
app.add_typer(cliadd.app, name="add",)
app.add_typer(cliclone.app, name="clone",)
app.add_typer(cliupdate.app, name="update",)
app.add_typer(cliupgrade.app, name="upgrade",)
app.add_typer(clibatch.app, name="batch",)
app.add_typer(clicaas.app, name="caas", hidden=True,)


class MoveArgs(str, Enum):
    site = "site"
    group = "group"


@app.command(
    short_help="Move device(s) to a defined group and/or site",
    help="Move device(s) to a defined group and/or site.",
)
def move(
    device: List[str, ] = typer.Argument(None, metavar=f"[{iden.dev} ...]", autocompletion=cli.cache.dev_kwarg_completion,),
    kw1: str = typer.Argument(
        None,
        metavar="",
        show_default=False,
        hidden=True,
    ),
    kw1_val: str = typer.Argument(
        None,
        metavar="[site <SITE>]",
        show_default=False,
    ),
    kw2: str = typer.Argument(
        None, metavar="",
        show_default=False,
        hidden=True,
    ),
    kw2_val: str = typer.Argument(
        None,
        metavar="[group <GROUP>]",
        show_default=False,
        help="[site and/or group required]",
    ),
    _group: str = typer.Option(
        None,
        "--group",
        help="Group to Move device(s) to",
        hidden=True,
        autocompletion=cli.cache.group_completion,
    ),
    _site: str = typer.Option(
        None, "--site",
        help="Site to move device(s) to",
        hidden=True,
        autocompletion=cli.cache.site_completion,
    ),
    yes: bool = typer.Option(False, "-Y", help="Bypass confirmation prompts - Assume Yes"),
    debug: bool = typer.Option(False, "--debug", envvar="ARUBACLI_DEBUG", help="Enable Additional Debug Logging"),
    default: bool = typer.Option(False, "-d", is_flag=True, help="Use default central account", show_default=False,),
    account: str = typer.Option("central_info",
                                envvar="ARUBACLI_ACCOUNT",
                                help="The Aruba Central Account to use (must be defined in the config)",
                                autocompletion=cli.cache.account_completion),
    # yes_: bool = typer.Option(False, "-y", hidden=True),
) -> None:
    central = cli.central

    group, site, = None, None
    for a, b in zip([kw1, kw2], [kw1_val, kw2_val]):
        if a == "group":
            group = b
        elif a == "site":
            site = b
        else:
            device += tuple([aa for aa in [a, b] if aa and aa not in ["group", "site"]])

    if not device:
        typer.echo("Error: Missing argument '[[name|ip|mac-address|serial] ...]'.")
        raise typer.Exit(1)

    group = group or _group
    site = site or _site

    if not group and not site:
        typer.secho("Missing Required Argument, group and/or site is required.")
        raise typer.Exit(1)

    dev = [cli.cache.get_dev_identifier(d) for d in device]
    devs_by_type = {
    }
    devs_by_site = {
    }
    dev_all_names, dev_all_serials, = [], []
    for d in dev:
        if d.generic_type not in devs_by_type:
            devs_by_type[d.generic_type] = [d]
        else:
            devs_by_type[d.generic_type] += [d]
        dev_all_names += [d.name]
        dev_all_serials += [d.serial]

        if site and d.site:
            if f"{d.site}~|~{d.generic_type}" not in devs_by_site:
                devs_by_site[f"{d.site}~|~{d.generic_type}"] = [d]
            else:
                devs_by_site[f"{d.site}~|~{d.generic_type}"] += [d]

    _s = "," if len(dev_all_names) > 2 else " &"
    _s = typer.style(_s, fg="bright_green")
    _msg_devs = f'{_s} '.join(typer.style(n, fg="reset") for n in dev_all_names)
    _msg_in_site = "" if not devs_by_site else typer.style(" (devices will be removed from current sites.)", fg="red")
    _msg_end = typer.style("?", fg="bright_green")
    _msg = None

    if group:
        _group = cli.cache.get_group_identifier(group)
        _msg = [
            typer.style("Please Confirm: move", fg="bright_green"),
            _msg_devs,
            typer.style("to group", fg="bright_green"),
            typer.style((_group.name), fg='reset'),
        ]
        _msg = f"{' '.join(_msg)}{_msg_end}"
    if site:
        _site = cli.cache.get_site_identifier(site)
        if not _msg:
            _msg = [
                typer.style("Please Confirm: move", fg="bright_green"),
                _msg_devs,
                typer.style("to site", fg="bright_green"),
                typer.style((_site.name), fg='reset'),
            ]
            _msg = f"{' '.join(_msg)}{_msg_in_site}{_msg_end}"
        else:
            _msg_site = typer.style((_site.name), fg=typer.colors.RESET)
            _msg = f'{_msg.replace("?", "")} {typer.style(f"and site", fg="bright_green")} {_msg_site}{_msg_in_site}{_msg_end}'

    resp, site_rm_resp = None, None
    confirmed = True if yes or typer.confirm(_msg, abort=True) else False

    # If devices are associated with a site currently remove them from that site first
    if confirmed and _site and devs_by_site:
        site_remove_reqs = []
        for [site_name, dev_type], devs in zip([k.split("~|~") for k in devs_by_site.keys()], list(devs_by_site.values())):
            site_remove_reqs += [
                central.BatchRequest(
                    central.remove_devices_from_site,
                    cli.cache.get_site_identifier(site_name).id,
                    serial_nums=[d.serial for d in devs],
                    device_type=dev_type,
                )
            ]
        site_rm_resp = central.batch_request(site_remove_reqs)
        if not all(r.ok for r in site_rm_resp):
            cli.display_results(site_rm_resp, tablefmt="action", exit_on_fail=True)

    # run both group and site move in parallel
    if confirmed and _group and _site:
        reqs = [central.BatchRequest(central.move_devices_to_group, _group.name, serial_nums=dev_all_serials)]
        site_remove_reqs = []
        for _type in devs_by_type:
            serials = [d.serial for d in devs_by_type[_type]]
            reqs += [
                central.BatchRequest(central.move_devices_to_site, _site.id, serial_nums=serials, device_type=_type)
            ]

        resp = central.batch_request(reqs)

    # only moving group via single API call
    elif confirmed and _group:
        resp = [
            cli.central.request(cli.central.move_devices_to_group, _group.name, serial_nums=dev_all_serials)
        ]

    # only moving site, potentially multiple calls (for each device_type)
    elif confirmed and _site:
        for _type in devs_by_type:
            serials = [d.serial for d in devs_by_type[_type]]
            reqs = [
                central.BatchRequest(central.move_devices_to_site, _site.id, serial_nums=serials, device_type=_type)
            ]

        resp = central.batch_request(reqs)

    if site_rm_resp:
        resp = [*site_rm_resp, *resp]

    cli.display_results(resp, tablefmt="action", ok_status=500)


@app.command(short_help="Bounce Interface or PoE on Interface")
def bounce(
    what: BounceArgs = typer.Argument(...),
    device: str = typer.Argument(..., metavar=iden.dev, autocompletion=cli.cache.dev_completion),
    port: str = typer.Argument(..., autocompletion=lambda incomplete: []),
    yes: bool = typer.Option(False, "-Y", help="Bypass confirmation prompts - Assume Yes"),
    yes_: bool = typer.Option(False, "-y", hidden=True),
    debug: bool = typer.Option(False, "--debug", envvar="ARUBACLI_DEBUG", help="Enable Additional Debug Logging",),
    default: bool = typer.Option(False, "-d", is_flag=True, help="Use default central account", show_default=False,),
    account: str = typer.Option("central_info",
                                envvar="ARUBACLI_ACCOUNT",
                                help="The Aruba Central Account to use (must be defined in the config)",
                                autocompletion=cli.cache.account_completion),
) -> None:
    yes = yes_ if yes_ else yes
    dev = cli.cache.get_dev_identifier(device)
    command = 'bounce_poe_port' if what == 'poe' else 'bounce_interface'
    if yes or typer.confirm(typer.style(f"Please Confirm bounce {what} on {dev.name} port {port}", fg="cyan")):
        resp = cli.central.request(cli.central.send_bounce_command_to_device, dev.serial, command, port)
        typer.secho(str(resp), fg="green" if resp else "red")
        # !! removing this for now Central ALWAYS returns:
        # !!   reason: Sending command to device. state: QUEUED, even after command execution.
        # if resp and resp.get('task_id'):
        #     resp = cli.central.request(session.get_task_status, resp.task_id)
        #     typer.secho(str(resp), fg="green" if resp else "red")

    else:
        raise typer.Abort()


@app.command(short_help="Remove a device from a site.")
def remove(
    devices: List[str] = typer.Argument(..., metavar=iden.dev_many, autocompletion=cli.cache.remove_completion),
    # _device: List[str] = typer.Argument(..., metavar=iden.dev, autocompletion=cli.cache.completion),
    # _site_kw: RemoveArgs = typer.Argument(None),
    site: str = typer.Argument(
        ...,
        metavar="[site <SITE>]",
        show_default=False,
        autocompletion=cli.cache.remove_completion
    ),
    yes: bool = typer.Option(False, "-Y", help="Bypass confirmation prompts - Assume Yes"),
    yes_: bool = typer.Option(False, "-y", hidden=True),
    debug: bool = typer.Option(False, "--debug", envvar="ARUBACLI_DEBUG", help="Enable Additional Debug Logging",),
    default: bool = typer.Option(False, "-d", is_flag=True, help="Use default central account", show_default=False,),
    account: str = typer.Option("central_info",
                                envvar="ARUBACLI_ACCOUNT",
                                help="The Aruba Central Account to use (must be defined in the config)",
                                autocompletion=cli.cache.account_completion),
) -> None:
    yes = yes_ if yes_ else yes
    devices = (d for d in devices if d != "site")
    devices = [cli.cache.get_dev_identifier(dev) for dev in devices]
    site = cli.cache.get_site_identifier(site)

    # TODO add confirmation method builder to output class
    if yes or typer.confirm(
        typer.style(f"Please Confirm remove {', '.join([dev.name for dev in devices])} from site {site.name}", fg="cyan")
    ):
        devs_by_type = {
        }
        for d in devices:
            if d.generic_type not in devs_by_type:
                devs_by_type[d.generic_type] = [d.serial]
            else:
                devs_by_type[d.generic_type] += [d.serial]
        reqs = [
            cli.central.BatchRequest(
                cli.central.remove_devices_from_site,
                site.id,
                serial_nums=serials,
                device_type=dev_type) for dev_type, serials in devs_by_type.items()
        ]
        resp = cli.central.batch_request(reqs)
        cli.display_results(resp, tablefmt="action")


@app.command(hidden=True)
def refresh(what: RefreshWhat = typer.Argument(...),
            debug: bool = typer.Option(False, "--debug", envvar="ARUBACLI_DEBUG", help="Enable Additional Debug Logging",),
            default: bool = typer.Option(False, "-d", is_flag=True, help="Use default central account", show_default=False,),
            account: str = typer.Option("central_info",
                                        envvar="ARUBACLI_ACCOUNT",
                                        help="The Aruba Central Account to use (must be defined in the config)",
                                        autocompletion=cli.cache.account_completion),
            ):
    """refresh <'token'|'cache'>"""

    central = CentralApi(account)

    if what.startswith("token"):
        from centralcli.response import Session
        Session(central.auth).refresh_token()
    else:  # cache is only other option
        cli.cache(refresh=True)


@app.command(hidden=True, epilog="Output is displayed in yaml by default.")
def method_test(method: str = typer.Argument(...),
                kwargs: List[str] = typer.Argument(None),
                do_json: bool = typer.Option(False, "--json", is_flag=True, help="Output in JSON", show_default=False),
                do_yaml: bool = typer.Option(False, "--yaml", is_flag=True, help="Output in YAML", show_default=False),
                do_csv: bool = typer.Option(False, "--csv", is_flag=True, help="Output in CSV", show_default=False),
                do_table: bool = typer.Option(False, "--table", is_flag=True, help="Output in Table", show_default=False),
                outfile: Path = typer.Option(None, help="Output to file (and terminal)", writable=True),
                no_pager: bool = typer.Option(True, "--pager", help="Enable Paged Output"),
                update_cache: bool = typer.Option(False, "-U", hidden=True),  # Force Update of cache for testing
                default: bool = typer.Option(False, "-d", is_flag=True, help="Use default central account", show_default=False,
                                             callback=cli.default_callback),
                debug: bool = typer.Option(False, "--debug", envvar="ARUBACLI_DEBUG", help="Enable Additional Debug Logging",
                                           callback=cli.debug_callback),
                account: str = typer.Option("central_info",
                                            envvar="ARUBACLI_ACCOUNT",
                                            help="The Aruba Central Account to use (must be defined in the config)",
                                            autocompletion=cli.cache.account_completion,
                                            ),
                ) -> None:
    """dev testing commands to run CentralApi methods from command line

    Args:
        method (str, optional): CentralAPI method to test.
        kwargs (List[str], optional): list of args kwargs to pass to function.

    format: arg1 arg2 keyword=value keyword2=value
        or  arg1, arg2, keyword = value, keyword2=value

    Displays all attributes of Response object
    """
    cli.cache(refresh=update_cache)
    central = CentralApi(account)
    if not hasattr(central, method):
        bpdir = Path(__file__).parent / "boilerplate"
        all_calls = [
            importlib.import_module(f"centralcli.{bpdir.name}.{f.stem}") for f in bpdir.iterdir()
            if not f.name.startswith("_") and f.suffix == ".py"
        ]
        for m in all_calls:
            if hasattr(m.AllCalls(), method):
                central = m.AllCalls()
                break

    if not hasattr(central, method):
        typer.secho(f"{method} does not exist", fg="red")
        raise typer.Exit(1)

    kwargs = (
        "~".join(kwargs).replace("'", "").replace('"', '').replace("~=", "=").replace("=~", "=").replace(",~", ",").split("~")
    )
    args = [k if not k.isdigit() else int(k) for k in kwargs if "=" not in k]
    kwargs = [k.split("=") for k in kwargs if "=" in k]
    kwargs = {k[0]: k[1] if not k[1].isdigit() else int(k[1]) for k in kwargs}
    for k, v in kwargs.items():
        if v.startswith("[") and v.endswith("]"):
            kwargs[k] = [vv if not vv.isdigit() else int(vv) for vv in v.strip("[]").split(",")]
        if v.lower() in ["true", "false"]:
            kwargs[k] = True if v.lower() == "true" else False

    from rich.console import Console
    c = Console(file=outfile)

    req = (
        f"central.{method}({', '.join(str(a) for a in args)}, "
        f"{', '.join([f'{k}={kwargs[k]}' for k in kwargs]) if kwargs else ''})"
    )

    resp = central.request(getattr(central, method), *args, **kwargs)
    if "should be str" in resp.output and "bool" in resp.output:
        c.log(f"{resp.output}.  LAME!  Converting to str!")
        args = tuple([str(a).lower() if isinstance(a, bool) else a for a in args])
        kwargs = {k: str(v).lower() if isinstance(v, bool) else v for k, v in kwargs.items()}
    resp = central.request(getattr(central, method), *args, **kwargs)

    attrs = {
        k: v for k, v in resp.__dict__.items() if k not in ["output", "raw"] and (log.DEBUG or not k.startswith("_"))
    }

    c.print(req)
    c.print("\n".join([f"  {k}: {v}" for k, v in attrs.items()]))

    tablefmt = cli.get_format(
        do_json, do_yaml, do_csv, do_table, default="yaml"
    )

    typer.echo(f"\n{typer.style('CentralCLI Response Output', fg='bright_green')}:")
    cli.display_results(data=resp.output, tablefmt=tablefmt, pager=not no_pager, outfile=outfile)
    if resp.raw:
        typer.echo(f"\n{typer.style('Raw Response Output', fg='bright_green')}:")
        cli.display_results(data=resp.raw, tablefmt="json", pager=not no_pager, outfile=outfile)


def all_commands_callback(ctx: typer.Context, debug: bool):
    if not ctx.resilient_parsing:
        account, debug, default, update_cache = None, None, None, None
        for idx, arg in enumerate(sys.argv):
            if arg == "--debug":
                debug = True
            elif arg == "-d":
                default = True
            elif arg == "--account" and "-d" not in sys.argv:
                account = sys.argv[idx + 1]
            elif arg == "-U":
                update_cache = True
            elif arg.startswith("-") and not arg.startswith("--"):
                if "d" in arg:
                    default = True
                if "U" in arg:
                    update_cache = True

        account = account or os.environ.get("ARUBACLI_ACCOUNT", False)
        debug = debug or os.environ.get("ARUBACLI_DEBUG", False)

        if default:
            default = cli.default_callback(ctx, True)
        elif account:
            cli.account_name_callback(ctx, account=account)
        if debug:
            cli.debug_callback(ctx, debug=debug)
        if update_cache:
            # cli.cache(refresh=True)
            # TODO can do cache update here once update is removed from all commands
            pass


@app.callback()
def callback(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", is_flag=True, envvar="ARUBACLI_DEBUG", help="Enable Additional Debug Logging",
                               callback=all_commands_callback),
    default: bool = typer.Option(False, "-d", is_flag=True, help="Use default central account", show_default=False,),
    account: str = typer.Option("central_info",
                                envvar="ARUBACLI_ACCOUNT",
                                help="The Aruba Central Account to use (must be defined in the config)",
                                autocompletion=cli.cache.account_completion),
    update_cache: bool = typer.Option(False, "-U", hidden=True),
) -> None:
    """
    Aruba Central API CLI
    """
    pass


log.debug(f'{__name__} called with Arguments: {" ".join(sys.argv)}')

if __name__ == "__main__":
    app()
