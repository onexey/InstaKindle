"""Tests for the retry decorator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from instakindle.retry import retry


class TestRetryDecorator:
    """Tests for the retry() decorator."""

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_succeeds_on_first_attempt(self, mock_sleep: MagicMock) -> None:
        """Function should return immediately when it succeeds."""
        func = MagicMock(return_value="ok")
        decorated = retry(max_attempts=3, exceptions=(ValueError,))(func)

        result = decorated()

        assert result == "ok"
        func.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_retries_on_matching_exception(self, mock_sleep: MagicMock) -> None:
        """Function should retry on matching exceptions and eventually succeed."""
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        decorated = retry(max_attempts=3, backoff_factor=2.0, exceptions=(ValueError,))(func)

        result = decorated()

        assert result == "ok"
        assert func.call_count == 3
        assert mock_sleep.call_count == 2
        # backoff_factor ** 0 = 1.0, backoff_factor ** 1 = 2.0
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_raises_after_max_attempts(self, mock_sleep: MagicMock) -> None:
        """Function should raise the last exception when all attempts fail."""
        func = MagicMock(side_effect=ValueError("persistent error"))
        decorated = retry(max_attempts=3, exceptions=(ValueError,))(func)

        with pytest.raises(ValueError, match="persistent error"):
            decorated()

        assert func.call_count == 3
        # Only 2 sleeps (between attempts, not after the last failure)
        assert mock_sleep.call_count == 2

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_does_not_retry_on_non_matching_exception(self, mock_sleep: MagicMock) -> None:
        """Function should not retry on exceptions not in the exceptions tuple."""
        func = MagicMock(side_effect=TypeError("wrong type"))
        decorated = retry(max_attempts=3, exceptions=(ValueError,))(func)

        with pytest.raises(TypeError, match="wrong type"):
            decorated()

        func.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_succeeds_on_second_attempt(self, mock_sleep: MagicMock) -> None:
        """Function should succeed on the second attempt after one failure."""
        func = MagicMock(side_effect=[ValueError("transient"), "recovered"])
        decorated = retry(max_attempts=3, exceptions=(ValueError,))(func)

        result = decorated()

        assert result == "recovered"
        assert func.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_custom_backoff_factor(self, mock_sleep: MagicMock) -> None:
        """Backoff should use the custom factor for exponential wait."""
        func = MagicMock(side_effect=[ValueError("1"), ValueError("2"), ValueError("3"), "ok"])
        decorated = retry(max_attempts=4, backoff_factor=3.0, exceptions=(ValueError,))(func)

        result = decorated()

        assert result == "ok"
        assert func.call_count == 4
        # 3.0 ** 0 = 1.0, 3.0 ** 1 = 3.0, 3.0 ** 2 = 9.0
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(3.0)
        mock_sleep.assert_any_call(9.0)

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_single_attempt(self, mock_sleep: MagicMock) -> None:
        """With max_attempts=1, there should be no retry."""
        func = MagicMock(side_effect=ValueError("fail"))
        decorated = retry(max_attempts=1, exceptions=(ValueError,))(func)

        with pytest.raises(ValueError, match="fail"):
            decorated()

        func.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_preserves_function_metadata(self, _mock_sleep: MagicMock) -> None:
        """Decorated function should preserve the original function's name and docstring."""

        @retry(max_attempts=2, exceptions=(ValueError,))
        def my_function() -> str:
            """My docstring."""
            return "value"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_passes_args_and_kwargs(self, _mock_sleep: MagicMock) -> None:
        """Decorated function should correctly forward arguments."""
        func = MagicMock(return_value="ok")
        decorated = retry(max_attempts=2, exceptions=(ValueError,))(func)

        decorated("a", "b", key="value")

        func.assert_called_once_with("a", "b", key="value")

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_multiple_exception_types(self, mock_sleep: MagicMock) -> None:
        """Should retry on any of the specified exception types."""
        func = MagicMock(side_effect=[ValueError("v"), OSError("o"), "ok"])
        decorated = retry(max_attempts=3, exceptions=(ValueError, OSError))(func)

        result = decorated()

        assert result == "ok"
        assert func.call_count == 3

    @patch("instakindle.retry.time.sleep", return_value=None)
    def test_logs_warning_on_retry(self, _mock_sleep: MagicMock) -> None:
        """Should log a warning for each retry attempt."""
        func = MagicMock(side_effect=[ValueError("fail"), "ok"])
        decorated = retry(max_attempts=3, exceptions=(ValueError,))(func)

        with patch("instakindle.retry.logger") as mock_logger:
            decorated()
            mock_logger.warning.assert_called_once()
            warning_args = mock_logger.warning.call_args[0]
            assert "1/3" in warning_args[0] % warning_args[1:]
