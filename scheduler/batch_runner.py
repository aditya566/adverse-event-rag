"""
scheduler/batch_runner.py

Daily batch job: collects all approved reportable events from the day,
generates MedWatch 3500A PDFs, and prepares them for submission.

This runs as a scheduled job (cron or APScheduler) at EOD each business day.

Submission methods supported:
  - Local folder drop (default for standalone tool)
  - SFTP (configure credentials in .env)
  - Email attachment
"""

import os
import json
import logging
import shutil
from datetime import datetime, date
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from report_generator.templates.medwatch_3500a import generate_medwatch_3500a
from config.settings import settings

logger = logging.getLogger(__name__)

# Directory where the review API writes approved cases
APPROVED_CASES_DIR = Path("./data/approved_cases")
SUBMISSION_QUEUE_DIR = Path(settings.REPORT_OUTPUT_DIR) / "submission_queue"
ARCHIVE_DIR = Path(settings.REPORT_OUTPUT_DIR) / "archive"


def load_approved_cases_for_today() -> list[dict]:
    """
    Load all cases approved by advocates today that are marked reportable.
    In production, this queries the case management database.
    For standalone tool: reads JSON files from approved_cases/ directory.
    """
    today_str = date.today().isoformat()
    cases = []

    if not APPROVED_CASES_DIR.exists():
        logger.warning(f"Approved cases directory not found: {APPROVED_CASES_DIR}")
        return cases

    for filepath in APPROVED_CASES_DIR.glob(f"{today_str}_*.json"):
        try:
            with open(filepath) as f:
                case = json.load(f)
            if case.get("advocate_decision") == "YES":
                cases.append(case)
                logger.info(f"Loaded approved case: {case.get('case_id')}")
        except Exception as e:
            logger.error(f"Failed to load case file {filepath}: {e}")

    logger.info(f"Found {len(cases)} reportable cases for {today_str}")
    return cases


def generate_reports_for_batch(cases: list[dict]) -> list[str]:
    """
    Generate MedWatch 3500A PDFs for each approved case.
    Returns list of generated file paths.
    """
    SUBMISSION_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    generated_files = []

    for case in cases:
        case_id = case.get("case_id", "UNKNOWN")
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"MedWatch3500A_{case_id}_{timestamp}.pdf"
            output_path = str(SUBMISSION_QUEUE_DIR / filename)

            generate_medwatch_3500a(
                classifier_output=case.get("classifier_output", {}),
                case_id=case_id,
                advocate_id=case.get("advocate_id", "UNKNOWN"),
                call_date=case.get("call_date", date.today().isoformat()),
                output_path=output_path,
            )

            generated_files.append(output_path)
            logger.info(f"Generated report: {filename}")

        except Exception as e:
            logger.error(f"Failed to generate report for case {case_id}: {e}")

    return generated_files


def submit_reports(report_files: list[str]) -> dict:
    """
    Submit generated reports to pharma manufacturers.
    Currently supports: local folder drop (default for standalone tool).

    For production: configure SFTP or email submission.
    """
    results = {"submitted": [], "failed": []}

    for filepath in report_files:
        try:
            # DEFAULT: Move to a designated outbox folder
            # In production, replace with SFTP upload or email
            outbox = Path(settings.REPORT_OUTPUT_DIR) / "outbox"
            outbox.mkdir(parents=True, exist_ok=True)
            dest = outbox / Path(filepath).name
            shutil.copy2(filepath, dest)

            logger.info(f"Report ready for submission: {dest}")
            results["submitted"].append(filepath)

            # Archive original
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(filepath, ARCHIVE_DIR / Path(filepath).name)

        except Exception as e:
            logger.error(f"Failed to submit {filepath}: {e}")
            results["failed"].append(filepath)

    return results


def run_daily_batch():
    """Main batch job — called by scheduler at EOD."""
    run_date = date.today().isoformat()
    logger.info(f"{'='*50}")
    logger.info(f"Starting daily adverse event report batch: {run_date}")
    logger.info(f"{'='*50}")

    cases = load_approved_cases_for_today()

    if not cases:
        logger.info("No reportable cases for today. Batch complete.")
        return

    report_files = generate_reports_for_batch(cases)
    logger.info(f"Generated {len(report_files)} reports")

    results = submit_reports(report_files)
    logger.info(
        f"Batch complete: {len(results['submitted'])} submitted, "
        f"{len(results['failed'])} failed"
    )

    # Write batch summary
    summary = {
        "date": run_date,
        "total_cases": len(cases),
        "reports_generated": len(report_files),
        "submitted": len(results["submitted"]),
        "failed": len(results["failed"]),
        "timestamp": datetime.utcnow().isoformat(),
    }
    summary_path = Path(settings.REPORT_OUTPUT_DIR) / f"batch_summary_{run_date}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Batch summary written to {summary_path}")


def start_scheduler():
    """Start the APScheduler to run the daily batch at the configured time."""
    hour, minute = settings.BATCH_SUBMISSION_TIME.split(":")

    scheduler = BlockingScheduler(timezone=settings.BATCH_TIMEZONE)
    scheduler.add_job(
        run_daily_batch,
        trigger=CronTrigger(hour=int(hour), minute=int(minute)),
        id="daily_adverse_event_batch",
        name="Daily Adverse Event Report Batch",
        misfire_grace_time=3600,  # Allow up to 1hr late start
    )

    logger.info(
        f"Scheduler started. Daily batch will run at "
        f"{settings.BATCH_SUBMISSION_TIME} {settings.BATCH_TIMEZONE}"
    )
    scheduler.start()


if __name__ == "__main__":
    # Run immediately (for testing or manual trigger)
    run_daily_batch()
