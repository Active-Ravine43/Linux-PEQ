"""Entry point: python -m peq_app [--tui|--gui]"""

import sys

import click


@click.command()
@click.option(
    "--ui",
    type=click.Choice(["tui", "gui"]),
    default="tui",
    help="Frontend interface (default: tui)",
)
@click.option(
    "--scan",
    is_flag=True,
    help="List audio applications and exit",
)
@click.option(
    "--create-eq",
    metavar="SINK_INPUT_ID",
    type=int,
    help="Create an EQ sink for the given sink-input ID and print details",
)
@click.option(
    "--theme",
    type=click.Choice(["amber", "slate", "mono", "forest", "copper", "plum", "ocean", "rosewood"]),
    default=None,
    help="Set the colour theme (persisted across sessions).",
)
def main(ui: str, scan: bool, create_eq: int | None, theme: str | None) -> None:
    """PEQ — Per-application Parametric Equalizer for Linux PipeWire."""
    if scan:
        from peq_app.audio_backend.scanner import PWNodeScanner

        scanner = PWNodeScanner()
        apps = scanner.scan()
        for app in apps:
            print(f"  {app.name} (id={app.sink_input_id}, sink={app.sink_id})")
        scanner.close()
        return

    if create_eq is not None:
        from peq_app.audio_backend.eq_engine import PWEQEngine

        engine = PWEQEngine()
        node_id = engine.create_eq_chain(f"app.{create_eq}")
        print(f"Created EQ sink: filter_node_id={node_id}")
        return

    if ui == "tui":
        from peq_app.ui_tui.app import run_app

        run_app(theme=theme)
    elif ui == "gui":
        click.echo("GTK4 GUI not yet implemented. Use --ui tui")
        sys.exit(1)


if __name__ == "__main__":
    # Click reads sys.argv automatically when invoked with no arguments.
    main()  # pylint: disable=no-value-for-parameter
