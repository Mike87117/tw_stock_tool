import logging
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.data.providers import yfinance_provider


class YfinanceProviderTest(unittest.TestCase):
    def test_forwards_arguments_and_restores_logger_state(self) -> None:
        logger = logging.getLogger("yfinance")
        state = (logger.disabled, logger.level, logger.propagate)
        expected = pd.DataFrame({"Close": [1]})
        with patch.object(yfinance_provider.yf, "download", return_value=expected) as download:
            self.assertIs(yfinance_provider.download_yfinance_quiet("2330.TW", "1y", "1d", False), expected)
        download.assert_called_once_with("2330.TW", period="1y", interval="1d", auto_adjust=False, progress=False, threads=False)
        self.assertEqual((logger.disabled, logger.level, logger.propagate), state)

    def test_restores_logger_state_when_provider_raises(self) -> None:
        logger = logging.getLogger("yfinance")
        state = (logger.disabled, logger.level, logger.propagate)
        with patch.object(yfinance_provider.yf, "download", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                yfinance_provider.download_yfinance_quiet("2330.TW", "1y", "1d", True)
        self.assertEqual((logger.disabled, logger.level, logger.propagate), state)