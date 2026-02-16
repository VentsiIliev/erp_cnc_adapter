"""Tests for src/core/logging_config.py — logging setup."""

import logging
from logging.handlers import RotatingFileHandler
from unittest.mock import patch

from src.core.logging_config import setup_logging


class TestSetupLogging:

    def test_creates_logs_directory(self):
        """setup_logging creates a logs/ directory and configures handlers."""
        setup_logging("INFO")
        root = logging.getLogger()
        assert len(root.handlers) >= 2

    def test_adds_file_and_stream_handler(self, tmp_path):
        setup_logging("INFO")
        root = logging.getLogger()
        handler_types = [type(h) for h in root.handlers]
        assert RotatingFileHandler in handler_types
        assert logging.StreamHandler in handler_types

    def test_respects_log_level(self, tmp_path):
        setup_logging("DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_invalid_level_falls_back_to_info(self):
        setup_logging("NOTAREALLEVEL")
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_clears_existing_handlers(self):
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        count_before = len(root.handlers)

        setup_logging("INFO")

        # After setup, should have exactly 2 handlers (file + stream)
        assert len(root.handlers) == 2
