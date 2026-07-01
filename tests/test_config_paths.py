import os
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib
import tw_stock_tool.utils.config

class TestConfigPaths(unittest.TestCase):
    def test_default_paths(self):
        # Remove env vars if present to test defaults
        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(tw_stock_tool.utils.config)
            
            # The config should resolve to cwd/output and cwd/cache
            expected_output = Path.cwd() / "output"
            expected_cache = Path.cwd() / "cache"
            
            self.assertEqual(tw_stock_tool.utils.config.OUTPUT_DIR, expected_output)
            self.assertEqual(tw_stock_tool.utils.config.CACHE_DIR, expected_cache)
            
            # Verify they are Path objects
            self.assertIsInstance(tw_stock_tool.utils.config.OUTPUT_DIR, Path)
            self.assertIsInstance(tw_stock_tool.utils.config.CACHE_DIR, Path)

    def test_env_var_overrides(self):
        # Set custom env vars
        custom_output = "/tmp/custom_output"
        custom_cache = "/tmp/custom_cache"
        env_vars = {
            "TW_STOCK_TOOL_OUTPUT_DIR": custom_output,
            "TW_STOCK_TOOL_CACHE_DIR": custom_cache,
        }
        
        with patch.dict(os.environ, env_vars):
            importlib.reload(tw_stock_tool.utils.config)
            
            self.assertEqual(tw_stock_tool.utils.config.OUTPUT_DIR, Path(custom_output))
            self.assertEqual(tw_stock_tool.utils.config.CACHE_DIR, Path(custom_cache))
            
            # Verify they are Path objects
            self.assertIsInstance(tw_stock_tool.utils.config.OUTPUT_DIR, Path)
            self.assertIsInstance(tw_stock_tool.utils.config.CACHE_DIR, Path)
            
    def tearDown(self):
        # Ensure we reload the module without env vars so subsequent tests 
        # (if any in the same runner) get a clean state.
        if "TW_STOCK_TOOL_OUTPUT_DIR" in os.environ:
            del os.environ["TW_STOCK_TOOL_OUTPUT_DIR"]
        if "TW_STOCK_TOOL_CACHE_DIR" in os.environ:
            del os.environ["TW_STOCK_TOOL_CACHE_DIR"]
        importlib.reload(tw_stock_tool.utils.config)

if __name__ == "__main__":
    unittest.main()