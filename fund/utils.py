# fund/utils.py
import yaml
import numpy as np
from typing import Any
from loguru import logger


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    logger.info(f"Loaded config from {config_path}")
    return config


def percentile_rank(values: list[float], target: float, reverse: bool = False) -> float:
    """
    计算 target 在 values 中的百分位排名 (0-100)。
    reverse=True 时值越小排名越高 (用于回撤、波动率等反向指标)。
    空列表返回 50.0 (中性分)。
    单个元素时返回 50.0。
    """
    n = len(values)
    if n <= 1:
        return 50.0
    arr = np.array(values)
    if reverse:
        rank = (arr > target).sum() / (n - 1) * 100.0
    else:
        rank = (arr < target).sum() / (n - 1) * 100.0
    return round(rank, 1)


def safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
