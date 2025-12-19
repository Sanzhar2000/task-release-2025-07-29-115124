"""
Command-line interface for the SWE-bench data downloader.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import sys

from .downloader import SWEBenchDownloader

console = Console()


@click.command()
@click.option(
    "--instance_id",
    help="Specific SWE-bench instance identifier (e.g., 'django__django-12345')",
)
@click.option(
    "--repo",
    help="Repository filter (e.g., 'django/django', 'flask/flask')",
)
@click.option(
    "--dataset",
    default="swe-bench",
    help="Dataset name ('swe-bench', 'swe-bench-lite', 'swe-bench-verified', etc.)",
)
@click.option(
    "--split",
    default="test",
    help="Data split ('train', 'test', 'dev')",
)
@click.option(
    "--difficulty",
    help="Filter by difficulty level (for datasets that support it)",
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of data points to download",
)
@click.option(
    "--start_idx",
    type=int,
    help="Starting index for range-based downloading",
)
@click.option(
    "--end_idx",
    type=int,
    help="Ending index for range-based downloading",
)
@click.option(
    "--output_dir",
    default="data_points",
    help="Output directory (default: data_points/)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def main(
    instance_id,
    repo,
    dataset,
    split,
    difficulty,
    limit,
    start_idx,
    end_idx,
    output_dir,
    force,
    verbose,
):
    """
    Download SWE-bench data points using the official SWE-bench library.
    
    Examples:
    
    # Download specific instance
    download_swe_bench.sh --instance_id "django__django-12345"
    
    # Download multiple instances from specific repository  
    download_swe_bench.sh --repo "django/django" --limit 10
    
    # Download by difficulty or dataset variant
    download_swe_bench.sh --dataset "swe-bench-lite" --limit 5
    
    # Download specific range
    download_swe_bench.sh --split "test" --start_idx 0 --end_idx 50
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Initialize downloader
        downloader = SWEBenchDownloader(
            dataset_name=dataset,
            split=split,
            output_dir=output_path,
            force_overwrite=force,
            verbose=verbose,
        )
        
        # Build filters
        filters = {}
        if instance_id:
            filters["instance_id"] = instance_id
        if repo:
            filters["repo"] = repo
        if difficulty:
            filters["difficulty"] = difficulty
        if start_idx is not None and end_idx is not None:
            filters["index_range"] = (start_idx, end_idx)
        
        # Download data points
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Loading dataset...", total=None)
            
            results = downloader.download(
                filters=filters,
                limit=limit,
                progress_callback=lambda desc: progress.update(task, description=desc),
            )
        
        # Display results summary
        console.print("\n[bold green]✓ Download completed successfully![/bold green]")
        console.print(f"[bold]Summary:[/bold]")
        console.print(f"  • Total downloaded: {results['downloaded']}")
        console.print(f"  • Skipped (existing): {results['skipped']}")
        console.print(f"  • Errors: {results['errors']}")
        console.print(f"  • Output directory: {output_dir}")
        
        if results["errors"] > 0:
            console.print(f"\n[yellow]Warning: {results['errors']} errors occurred during download[/yellow]")
            
        if verbose and results.get("error_details"):
            console.print("\n[bold]Error details:[/bold]")
            for error in results["error_details"]:
                console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]✗ Error: {str(e)}[/bold red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main() 