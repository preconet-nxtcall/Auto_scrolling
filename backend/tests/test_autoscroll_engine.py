import subprocess
from app.config import settings


def test_autoscroll_engine_javascript_state_machine():
    """
    Executes the AutoScrollEngine Node.js unit test suite to verify:
    1. Timing defaults (scrollSpeed=50, repeatCount=3, interactionPause=3000, startDelay=2000, betweenRepeatsDelay=1000)
    2. State machine transitions (IDLE -> STARTING -> SCROLLING -> PAUSED_BY_USER -> RETURNING_TO_TOP -> BETWEEN_REPEATS -> COMPLETED)
    3. 3-second user interaction pause and resume
    4. Manual scroll to bottom cycle completion
    5. Graceful handling of non-scrollable documents
    6. Event listener and timer handle cleanup on destroy
    """
    js_test_script = settings.BASE_DIR / "frontend" / "js" / "test_autoscroll_engine.js"
    assert js_test_script.exists(), f"Test script missing at '{js_test_script}'"

    result = subprocess.run(
        ["node", str(js_test_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15
    )

    assert result.returncode == 0, f"AutoScrollEngine Node.js unit test failed:\n{result.stderr or result.stdout}"
    assert "passed with zero errors!" in result.stdout

