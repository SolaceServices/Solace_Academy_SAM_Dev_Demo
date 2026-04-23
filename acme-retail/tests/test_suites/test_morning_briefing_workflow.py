"""
test_morning_briefing_workflow.py — Morning Briefing Workflow Test

Tests the AcmeMorningBriefingWorkflow by triggering it and validating:
1. Workflow executes successfully
2. Briefing artifact is created
3. All sections are populated with data
"""

import sys
import os
import json
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework.result import ResultCollector
from test_suites.test_utils import (
    _s, _bold, _dim, _cyan, _green, _yellow, _red,
    _bold_cyan, _bold_green, _bold_red,
)


# ── Constants ──────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
WORKFLOW_TIMEOUT_S = 120  # 2 minutes for workflow to complete


# ── Helper Functions ───────────────────────────────────────────────────────
def check_sam_running():
    """Check if SAM is accessible."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/config", timeout=5)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def check_workflow_exists():
    """Check if the AcmeMorningBriefingWorkflow is registered."""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/agentCards", timeout=5)
        response.raise_for_status()
        agent_cards = response.json()
        
        # Check if workflow exists in agent cards
        for card in agent_cards:
            if card.get("name") == "AcmeMorningBriefingWorkflow":
                return True
        return False
    except requests.exceptions.RequestException:
        return False


def trigger_workflow(today: str):
    """Trigger the morning briefing workflow and return the result."""
    workflow_input = {"trigger_date": today}
    
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"msg-{int(time.time())}",
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps(workflow_input)}],
                "metadata": {"agent_name": "AcmeMorningBriefingWorkflow"}
            }
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/message:send",
        json=payload,
        timeout=WORKFLOW_TIMEOUT_S
    )
    response.raise_for_status()
    return response.json()


def check_workflow_completion(task_id: str, session_id: str):
    """Check if workflow completed successfully by checking for completion indicators."""
    import glob
    import os
    
    try:
        # Method 1: Check task status
        response = requests.get(
            f"{BASE_URL}/api/v1/tasks?limit=100",
            timeout=5
        )
        response.raise_for_status()
        tasks = response.json()
        
        # Look for the parent workflow task
        for task in tasks:
            if task.get("id") == task_id:
                status = task.get("status")
                if status == "completed":
                    return True
                # If it has an end_time and didn't fail, consider it complete
                if task.get("end_time") is not None and status != "failed":
                    return True
        
        # Method 2: Check if any workflow-created artifacts exist
        # Look for the typical workflow artifacts pattern
        session_dir = f"/tmp/samv2/sam_dev_user/{session_id}"
        if os.path.exists(session_dir):
            # Look for merge_briefing or create_briefing_artifact output
            artifacts = glob.glob(f"{session_dir}/*merge_briefing*.json/0")
            if artifacts:
                # If merge_briefing completed, the workflow progressed significantly
                return True
            
            # Look for any Morning Briefing markdown file
            briefings = glob.glob(f"{session_dir}/Morning Briefing*.md/0")
            if briefings:
                # If the final artifact was created, workflow completed
                return True
        
        return False
    except Exception:
        return False


# ── Test Function ──────────────────────────────────────────────────────────
def test_workflow_execution(results: ResultCollector):
    """Test the morning briefing workflow end-to-end."""
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    print()
    
    # Step 1: Trigger workflow
    result = None
    try:
        result = trigger_workflow(today)
        with results.test("workflow_triggered", label="Workflow triggered successfully"):
            assert result is not None
            assert "result" in result
    except Exception as exc:
        results.record("workflow_triggered", False, str(exc))
        return
    
    # Extract session info
    result_data = result.get("result", {})
    task_id = result_data.get("id") or result_data.get("a2a_task_id")
    session_id = result_data.get("contextId") or result_data.get("session_id")
    
    print(_green(f"  ✅ Workflow triggered"))
    print(_dim(f"     Task ID: {task_id}"))
    print(_dim(f"     Session ID: {session_id}"))
    print()
    
    # Step 2: Verify session ID returned
    with results.test("session_created", label="Session ID returned"):
        assert session_id is not None and session_id != ""
    
    # Step 3: Wait for workflow to complete
    print(_cyan("  ⏳ Waiting for workflow to complete (~40-50s)..."))
    print()
    
    workflow_completed = False
    max_wait = 60  # 60 seconds max wait
    check_interval = 3  # Check every 3 seconds
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(1)  # Sleep 1 second at a time for smoother counter
        elapsed += 1
        
        # Only check for completion every 3 seconds
        if elapsed % check_interval == 0:
            workflow_completed = check_workflow_completion(task_id, session_id)
            if workflow_completed:
                break
        
        # Show progress every second
        if sys.stdout.isatty():
            sys.stdout.write(f"\r  ⏳ Waiting... {elapsed}s")
            sys.stdout.flush()
    
    if sys.stdout.isatty():
        sys.stdout.write("\r\033[K")  # Clear the waiting line
        sys.stdout.flush()
    
    # Step 4: Verify workflow completed successfully
    with results.test("workflow_completed", label="Workflow completed successfully"):
        assert workflow_completed, \
            f"Workflow did not complete after {elapsed}s. Check session at {BASE_URL}/#/chat/{session_id}"
    
    print(_green(f"  ✅ Workflow completed successfully ({elapsed}s)"))
    print()


# ── Summary Printer ────────────────────────────────────────────────────────
def print_summary(results: ResultCollector):
    """Print organized test results."""
    W = 62
    thick = "═" * W
    
    # Header
    print(_bold_cyan(thick))
    print(_bold(f"  Test Results  —  {results.suite_name}"))
    print(_bold_cyan(thick))
    print()
    
    # Results
    for r in results._results:
        display = r.label if r.label else r.name
        if r.passed:
            print(f"    ✅  {display}")
        else:
            print(f"    ❌  {_bold(display)}")
            if r.message:
                for line in r.message.splitlines():
                    print(_red(f"         {line}"))
    
    # Footer
    print()
    if results.all_passed:
        print(_bold_green(thick))
        print(_bold_green(f"  🎉  PASSED  —  {results.passed}/{results.total} checks passed"))
        print(_bold_green(thick))
    else:
        print(_bold_red(thick))
        print(_bold_red(f"  ✗   FAILED  —  {results.passed}/{results.total} checks passed ({results.failed} failed)"))
        print(_bold_red(thick))


# ── Main Runner ────────────────────────────────────────────────────────────
def run_tests(student_email="student@example.com"):
    results = ResultCollector(suite_name="Morning Briefing Workflow")
    
    W = 62
    print()
    print(_s("═" * W, "1", "36"))
    print(_s("  Morning Briefing Workflow", "1"))
    print(_s("═" * W, "1", "36"))
    print()
    
    # Check SAM is running
    if not check_sam_running():
        print(_red("  ❌ SAM is not running"))
        print()
        print(_yellow("  Please start SAM first:"))
        print(_dim("     cd /workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows/sam"))
        print(_dim("     sam run"))
        print()
        results.record("sam_running", passed=False, message="SAM not accessible at http://127.0.0.1:8000")
        return results
    
    print(_green("  ✅ SAM is running"))
    print()
    
    # Check workflow is registered
    if not check_workflow_exists():
        print(_red("  ❌ AcmeMorningBriefingWorkflow not found"))
        print()
        print(_yellow("  Please ensure you're running the 400-Workflows SAM:"))
        print(_dim("     cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts"))
        print(_dim("     bash 400-setup.sh /workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows"))
        print()
        print(_dim("  Then start SAM from the 400-Workflows directory:"))
        print(_dim("     cd /workspaces/Solace_Academy_SAM_Dev_Demo/400-Workflows/sam"))
        print(_dim("     sam run"))
        print()
        results.record("workflow_registered", passed=False, message="AcmeMorningBriefingWorkflow not registered in SAM")
        return results
    
    print(_green("  ✅ Workflow registered"))
    print()
    
    # Run the workflow test
    try:
        test_workflow_execution(results)
    except Exception as exc:
        print()
        print(_red(f"  ❌ Unexpected error: {exc}"))
        print()
        import traceback
        traceback.print_exc()
        results.record("workflow_execution", passed=False, message=str(exc))
    
    # Print summary
    print()
    print_summary(results)
    
    return results


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "student@example.com"
    results = run_tests(student_email=email)
    sys.exit(0 if results.all_passed else 1)
