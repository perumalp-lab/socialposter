"""Publisher orchestrator – validates and publishes to all target platforms."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from rich.console import Console
from rich.table import Table

from socialposter.core.content import PostFile, load_content
from socialposter.platforms.base import BasePlatform, PostResult
from socialposter.platforms.registry import PlatformRegistry
from socialposter.utils.logger import get_logger

# Ensure all platform plugins are imported / registered
import socialposter.platforms  # noqa: F401

logger = get_logger()
console = Console()


def _resolve_platforms(
    content: PostFile,
    filter_names: Optional[list[str]] = None,
) -> list[BasePlatform]:
    """Determine which platforms to publish to.

    Priority:
    1. --platforms flag (filter_names)
    2. Platforms enabled in the content file
    """
    enabled = content.enabled_platforms()

    if filter_names:
        # Only keep platforms that are both requested AND enabled in content
        names = [n.strip().lower() for n in filter_names]
        # Allow even if not in content — just use defaults
        target_names = names
    else:
        target_names = enabled

    platforms: list[BasePlatform] = []
    for name in target_names:
        try:
            platforms.append(PlatformRegistry.create(name))
        except ValueError:
            console.print(f"[yellow]Warning: Unknown platform '{name}', skipping[/yellow]")

    return platforms


def _publish_one(platform: BasePlatform, content: PostFile, dry_run: bool, user_id: int) -> PostResult:
    """Authenticate, validate, and publish to a single platform."""
    # Authenticate
    try:
        authenticated = platform.authenticate(user_id)
    except Exception as exc:
        return PostResult(
            success=False,
            platform=platform.name,
            error_message=str(exc),
        )
    if not authenticated:
        return PostResult(
            success=False,
            platform=platform.name,
            error_message="Authentication failed",
        )

    # Validate
    errors = platform.validate(content, user_id)
    if errors:
        return PostResult(
            success=False,
            platform=platform.name,
            error_message=" | ".join(errors),
        )

    # Dry run – skip actual publishing
    if dry_run:
        return PostResult(
            success=True,
            platform=platform.name,
            post_id="DRY_RUN",
            post_url="(dry run – no post created)",
        )

    # Publish
    return platform.publish(content, user_id)


def publish_all(
    content_file: str,
    platforms_filter: Optional[list[str]] = None,
    dry_run: bool = False,
    parallel: bool = True,
    user_id: int = 0,
) -> list[PostResult]:
    """Main entry point: load content, resolve platforms, publish, and report.

    Args:
        content_file: Path to the YAML/JSON content file.
        platforms_filter: Optional list of platform names to target.
        dry_run: If True, validate only – do not publish.
        parallel: If True, publish to platforms concurrently.
        user_id: The authenticated user's ID.

    Returns:
        List of PostResult objects.
    """
    # Load content
    try:
        content = load_content(content_file)
    except Exception as e:
        console.print(f"[red]Failed to load content file: {e}[/red]")
        return []

    # Resolve platforms
    platforms = _resolve_platforms(content, platforms_filter)
    if not platforms:
        console.print("[yellow]No platforms to publish to. Check your content file or --platforms flag.[/yellow]")
        return []

    mode_label = "[bold yellow]DRY RUN[/bold yellow]" if dry_run else "[bold green]PUBLISHING[/bold green]"
    console.print(f"\n{mode_label} to {len(platforms)} platform(s): "
                  f"{', '.join(p.display_name for p in platforms)}\n")

    results: list[PostResult] = []

    if parallel and len(platforms) > 1 and not dry_run:
        with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
            futures = {
                executor.submit(_publish_one, p, content, dry_run, user_id): p
                for p in platforms
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                _print_result_inline(result)
    else:
        for platform in platforms:
            result = _publish_one(platform, content, dry_run, user_id)
            results.append(result)
            _print_result_inline(result)

    # Summary table
    _print_summary(results)

    return results


def _print_result_inline(result: PostResult) -> None:
    """Print a single result as it completes."""
    if result.success:
        icon = "[green][OK][/green]"
        detail = result.post_url or result.post_id or "OK"
    else:
        icon = "[red][FAIL][/red]"
        detail = result.error_message or "Unknown error"
    console.print(f"  {icon} {result.platform:12s} → {detail}")


def _print_summary(results: list[PostResult]) -> None:
    """Print a summary table of all results."""
    table = Table(title="\nPublish Summary", show_lines=True)
    table.add_column("Platform", style="bold")
    table.add_column("Status")
    table.add_column("Post URL / Error")

    for r in sorted(results, key=lambda x: x.platform):
        status = "[green]Success[/green]" if r.success else "[red]Failed[/red]"
        detail = r.post_url or r.error_message or ""
        table.add_row(r.platform.title(), status, detail[:80])

    console.print(table)

    succeeded = sum(1 for r in results if r.success)
    total = len(results)
    console.print(f"\n[bold]{succeeded}/{total} platforms succeeded.[/bold]\n")
