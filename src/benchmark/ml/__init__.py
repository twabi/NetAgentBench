"""
ML model integration for the benchmark system.

Supports running pre-trained ML models for network configuration generation.
Models are loaded from checkpoints and used for inference only.
"""
from benchmark.ml.model_testee import MLModelTestee

__all__ = ["MLModelTestee"]

