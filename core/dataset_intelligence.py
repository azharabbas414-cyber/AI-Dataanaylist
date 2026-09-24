"""Single entry point for InsightAI's dataset intelligence layer."""
from __future__ import annotations
from typing import Any
import pandas as pd

from core.dataset_metadata import create_metadata
from core.profiler import profile_dataframe
from core.dataset_detector import detect_dataset_type, get_dataset_capabilities
from core.network_intelligence import analyze_network_capture


def build_dataset_intelligence(
    df: pd.DataFrame,
    source_name: str | None = None,
    source_type: str | None = None,
    capture_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dataset_type = detect_dataset_type(df, source_name, source_type)
    metadata = create_metadata(df, source_name, source_type)
    profile = profile_dataframe(df)
    capabilities = get_dataset_capabilities(dataset_type)

    intelligence: dict[str, Any] = {
        "metadata": metadata,
        "profile": profile,
        "dataset_type": dataset_type,
        "capabilities": capabilities,
    }

    if dataset_type == "network_capture":
        intelligence["network"] = analyze_network_capture(df, capture_metadata)
    else:
        intelligence["network"] = None

    return intelligence
