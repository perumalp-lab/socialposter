"""Click CLI for SocialPoster."""

from __future__ import annotations

import click

from socialposter import __version__


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="socialposter")
@click.pass_context
def main(ctx: click.Context) -> None:
    """SocialPoster – multi-platform social media publishing tool."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------

@main.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address")
@click.option("--port", default=5000, show_default=True, type=int, help="Port number")
@click.option("--debug/--no-debug", default=True, show_default=True, help="Enable debug mode")
def serve(host: str, port: int, debug: bool) -> None:
    """Launch the SocialPoster web server."""
    from socialposter.web.app import create_app

    app = create_app()
    app.run(host=host, port=port, debug=debug)


# ---------------------------------------------------------------------------
# post
# ---------------------------------------------------------------------------

@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=False, help="Validate only, do not publish")
@click.option("--platforms", default=None, help="Comma-separated list of platforms to target")
@click.option("--user-id", default=0, type=int, show_default=True, help="User ID for authentication")
def post(file: str, dry_run: bool, platforms: str | None, user_id: int) -> None:
    """Publish content from a YAML/JSON file."""
    from socialposter.web.app import create_app
    from socialposter.core.publisher import publish_all

    platform_list = [p.strip() for p in platforms.split(",")] if platforms else None

    app = create_app()
    with app.app_context():
        results = publish_all(
            content_file=file,
            platforms_filter=platform_list,
            dry_run=dry_run,
            user_id=user_id,
        )
    succeeded = sum(1 for r in results if r.success)
    raise SystemExit(0 if succeeded == len(results) else 1)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@main.command()
@click.argument("file", type=click.Path(exists=True))
def validate(file: str) -> None:
    """Validate a content YAML/JSON file without publishing."""
    from socialposter.core.content import load_content
    from rich.console import Console

    console = Console()
    try:
        content = load_content(file)
        enabled = content.enabled_platforms()
        console.print(f"[green]Valid.[/green] Enabled platforms: {', '.join(enabled) or 'none'}")
    except Exception as e:
        console.print(f"[red]Invalid:[/red] {e}")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# platforms
# ---------------------------------------------------------------------------

@main.command()
def platforms() -> None:
    """List all registered platform plugins."""
    from rich.console import Console
    from rich.table import Table
    from socialposter.platforms.registry import PlatformRegistry

    # Ensure plugins are imported
    import socialposter.platforms  # noqa: F401

    table = Table(title="Registered Platforms")
    table.add_column("Name", style="bold")
    table.add_column("Display Name")
    table.add_column("Post Types")
    table.add_column("Max Text")

    for name in PlatformRegistry.names():
        cls = PlatformRegistry.get(name)
        instance = cls()
        table.add_row(
            name,
            instance.display_name,
            ", ".join(t.value for t in instance.supported_post_types),
            str(instance.max_text_length) if instance.max_text_length else "–",
        )

    Console().print(table)


# ---------------------------------------------------------------------------
# db (migrations)
# ---------------------------------------------------------------------------

@main.group()
def db() -> None:
    """Database migration commands (Flask-Migrate / Alembic)."""


@db.command()
def upgrade() -> None:
    """Run pending database migrations."""
    from socialposter.web.app import create_app
    from flask_migrate import upgrade as _upgrade

    app = create_app()
    with app.app_context():
        _upgrade()
    click.echo("Database upgraded.")


@db.command()
def downgrade() -> None:
    """Revert the last database migration."""
    from socialposter.web.app import create_app
    from flask_migrate import downgrade as _downgrade

    app = create_app()
    with app.app_context():
        _downgrade()
    click.echo("Database downgraded.")
