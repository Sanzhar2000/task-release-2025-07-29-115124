"""
Core downloader functionality for SWE-bench data points.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from datasets import load_dataset
from rich.console import Console

# SWE-bench library imports
from swebench.harness.utils import load_swebench_dataset
from swebench.harness.constants import SWEbenchInstance, KEY_INSTANCE_ID

console = Console()
logger = logging.getLogger(__name__)


class SWEBenchDownloader:
    """
    Downloads and saves SWE-bench data points using the official datasets library.
    """
    
    # Additional dataset name mappings (SWE-bench library handles basic ones)
    DATASET_MAPPINGS = {
        "swe-bench-verified": "SWE-bench/SWE-bench_Verified",
        "swebench-verified": "SWE-bench/SWE-bench_Verified", 
        "swe_bench_verified": "SWE-bench/SWE-bench_Verified",
        "verified": "SWE-bench/SWE-bench_Verified",
        "swe-bench-multimodal": "SWE-bench/SWE-bench_Multimodal",
        "swebench-multimodal": "SWE-bench/SWE-bench_Multimodal",
        "swe_bench_multimodal": "SWE-bench/SWE-bench_Multimodal",
        "multimodal": "SWE-bench/SWE-bench_Multimodal",
        "swe-bench-multilingual": "SWE-bench/SWE-bench_Multilingual",
        "swebench-multilingual": "SWE-bench/SWE-bench_Multilingual",
        "swe_bench_multilingual": "SWE-bench/SWE-bench_Multilingual",
        "multilingual": "SWE-bench/SWE-bench_Multilingual",
    }
    
    def __init__(
        self,
        dataset_name: str = "swe-bench", 
        split: str = "test",
        output_dir: Path = Path("data_points"),
        force_overwrite: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize the SWE-bench downloader.
        
        Args:
            dataset_name: Name of the SWE-bench dataset variant
            split: Dataset split (train, test, dev)
            output_dir: Directory to save downloaded data points
            force_overwrite: Whether to overwrite existing files
            verbose: Enable verbose logging
        """
        self.dataset_name = self._normalize_dataset_name(dataset_name)
        self.split = split
        self.output_dir = Path(output_dir)
        self.force_overwrite = force_overwrite
        self.verbose = verbose
        
        # Setup logging
        if verbose:
            logging.basicConfig(level=logging.INFO)
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Load dataset
        self.dataset = None
        
    def _normalize_dataset_name(self, name: str) -> str:
        """Normalize dataset name to official Hugging Face format."""
        normalized = name.lower().replace("_", "-")
        return self.DATASET_MAPPINGS.get(normalized, name)
    
    def _load_dataset(self, progress_callback: Optional[Callable] = None, instance_ids: Optional[List[str]] = None):
        """Load the SWE-bench dataset using official SWE-bench library."""
        if self.dataset is not None:
            return
            
        if progress_callback:
            progress_callback(f"Loading {self.dataset_name} dataset...")
            
        try:
            self.dataset = load_swebench_dataset(
                name=self.dataset_name,
                split=self.split,
                instance_ids=instance_ids
            )
            if self.verbose:
                console.print(f"✓ Loaded {len(self.dataset)} instances from {self.dataset_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to load dataset '{self.dataset_name}': {str(e)}")
    
    def _apply_filters(self, filters: Dict[str, Any]) -> List[SWEbenchInstance]:
        """Apply filters to the dataset and return matching instances."""
        if not self.dataset:
            return []
            
        instances = list(self.dataset)
        
        # Note: instance_id filtering is now handled in _load_dataset via load_swebench_dataset
        
        # Filter by repository
        if "repo" in filters:
            target_repo = filters["repo"]
            instances = [inst for inst in instances if inst["repo"] == target_repo]
            
        # Filter by difficulty (if field exists)
        if "difficulty" in filters:
            target_difficulty = filters["difficulty"]
            instances = [
                inst for inst in instances 
                if inst.get("difficulty") == target_difficulty
            ]
            
        # Apply index range
        if "index_range" in filters:
            start_idx, end_idx = filters["index_range"]
            instances = instances[start_idx:end_idx + 1]
            
        return instances
    
    def _save_instance(self, instance: SWEbenchInstance) -> tuple[bool, Optional[str]]:
        """
        Save a single instance to JSON file.
        
        Returns:
            (success, error_message)
        """
        try:
            instance_id = instance["instance_id"]
            filename = f"{instance_id}.json"
            filepath = self.output_dir / filename
            
            # Check if file exists and force is not set
            if filepath.exists() and not self.force_overwrite:
                return False, None  # Skipped, not an error
                
            # Add metadata
            instance_with_metadata = {
                **instance,
                "_download_metadata": {
                    "downloaded_at": datetime.utcnow().isoformat(),
                    "dataset_name": self.dataset_name,
                    "split": self.split,
                    "downloader_version": "0.1.0",
                }
            }
            
            # Save to file
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(instance_with_metadata, f, indent=2, ensure_ascii=False)
                
            return True, None
            
        except Exception as e:
            return False, f"Failed to save {instance.get('instance_id', 'unknown')}: {str(e)}"
    
    def download(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Download filtered SWE-bench data points.
        
        Args:
            filters: Dictionary of filters to apply
            limit: Maximum number of instances to download
            progress_callback: Callback function for progress updates
            
        Returns:
            Dictionary with download statistics
        """
        filters = filters or {}
        
        # Extract instance_id for efficient loading
        instance_ids = None
        if "instance_id" in filters:
            instance_ids = [filters["instance_id"]]
        
        # Load dataset with instance_id filtering at load time
        self._load_dataset(progress_callback, instance_ids)
        
        if progress_callback:
            progress_callback("Applying filters...")
            
        # Apply remaining filters (repo, difficulty, index_range)
        filtered_instances = self._apply_filters(filters)
        
        # Apply limit
        if limit and len(filtered_instances) > limit:
            filtered_instances = filtered_instances[:limit]
            
        if not filtered_instances:
            if self.verbose:
                console.print("[yellow]No instances match the specified filters[/yellow]")
            return {
                "downloaded": 0,
                "skipped": 0,
                "errors": 0,
                "error_details": [],
            }
        
        if progress_callback:
            progress_callback(f"Downloading {len(filtered_instances)} instances...")
            
        # Download instances
        downloaded = 0
        skipped = 0
        errors = 0
        error_details = []
        
        for i, instance in enumerate(filtered_instances):
            if progress_callback:
                progress_callback(f"Downloading {i+1}/{len(filtered_instances)}: {instance['instance_id']}")
                
            success, error = self._save_instance(instance)
            
            if success:
                downloaded += 1
                if self.verbose:
                    console.print(f"✓ Downloaded: {instance['instance_id']}")
            elif error is None:
                skipped += 1
                if self.verbose:
                    console.print(f"⚠ Skipped (exists): {instance['instance_id']}")
            else:
                errors += 1
                error_details.append(error)
                if self.verbose:
                    console.print(f"✗ Error: {error}")
                    
        return {
            "downloaded": downloaded,
            "skipped": skipped, 
            "errors": errors,
            "error_details": error_details,
        } 