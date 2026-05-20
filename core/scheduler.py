"""
Scheduler module
Handles scheduled task scheduling and process monitoring
"""

import threading
import time
import logging
import schedule
import psutil
import os
from datetime import datetime, timedelta

# Import configuration
from config import config

class TaskScheduler:
    """Task scheduler that manages scheduled task execution"""

    def __init__(self, schedule_time=config.SCHEDULE_TIME):
        """Initialize the scheduler"""
        self.schedule_time = schedule_time
        self.stop_event = threading.Event()
        self.scheduler_thread = None
        self.process_monitor_thread = None
        self._scheduled_task = None  # Store the registered task function

    def schedule_daily_task(self, task_func):
        """Set up a daily scheduled task"""
        logging.info(f"📅 Daily task scheduled at {self.schedule_time}")
        schedule.every().day.at(self.schedule_time).do(task_func)
        self._scheduled_task = task_func  # Save reference to the task function

        # Return the job for testing convenience
        return schedule.jobs[-1]

    def run_immediately(self, task_func):
        """Execute a task immediately"""
        logging.info("🔄 Executing task immediately")
        try:
            return task_func()
        except Exception as e:
            logging.error(f"❌ Error executing immediate task: {e}")
            return None

    def start(self, run_now=True):
        """
        Start the scheduler
        Args:
            run_now: Whether to execute the task once immediately
        """
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logging.warning("⚠️ Scheduler is already running")
            return

        self.stop_event.clear()

        # If run_now=True and a task is registered, execute it immediately
        if run_now and self._scheduled_task:
            logging.info("🔄 Running backup task on startup as requested")
            # Execute in a new thread to avoid blocking the startup process
            immediate_thread = threading.Thread(
                target=self.run_immediately,
                args=(self._scheduled_task,),
                daemon=True
            )
            immediate_thread.start()

        # Start the scheduler thread — set as non-daemon to prevent the program from exiting when the main thread ends
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=False  # Changed to non-daemon thread
        )
        self.scheduler_thread.start()

        # Log the next scheduled execution time
        next_job = None
        for job in schedule.jobs:
            if not next_job or (job.next_run and job.next_run < next_job.next_run):
                next_job = job

        if next_job and next_job.next_run:
            logging.info(f"⏰ Next scheduled execution time: {next_job.next_run.strftime('%Y-%m-%d %H:%M:%S')}")

        return self.scheduler_thread

    def stop(self):
        """Stop the scheduler"""
        self.stop_event.set()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=1.0)

        if self.process_monitor_thread and self.process_monitor_thread.is_alive():
            self.process_monitor_thread.join(timeout=1.0)

        logging.info("✅ Scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        # Record the last time a heartbeat log was written
        last_log_time = datetime.now()

        # Use dynamic sleep time to optimise CPU usage
        while not self.stop_event.is_set():
            # Run any pending tasks
            schedule.run_pending()

            # Calculate time until the next task
            next_run = self._calculate_next_run_seconds()

            # Log a heartbeat once per hour to confirm the scheduler is still running
            now = datetime.now()
            if (now - last_log_time).total_seconds() >= 3600:  # 1 hour
                next_job = None
                for job in schedule.jobs:
                    if not next_job or (job.next_run and job.next_run < next_job.next_run):
                        next_job = job

                if next_job and next_job.next_run:
                    logging.info(f"🔄 Scheduler running, next execution time: {next_job.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logging.info("🔄 Scheduler running, but no tasks scheduled")

                last_log_time = now

            # Set dynamic sleep time
            sleep_time = min(next_run, config.SCHEDULE_CHECK_INTERVAL)

            # Interruptible sleep
            self.stop_event.wait(timeout=sleep_time)

    def _calculate_next_run_seconds(self):
        """Calculate the number of seconds until the next scheduled task"""
        # Default check interval
        default_interval = config.SCHEDULE_CHECK_INTERVAL

        # Find the next job to run
        next_job = None
        for job in schedule.jobs:
            next_run = job.next_run
            if next_run and (next_job is None or next_run < next_job.next_run):
                next_job = job

        if next_job is None:
            return default_interval

        # Calculate seconds until next run
        if next_job.next_run:
            now = datetime.now()
            time_delta = (next_job.next_run - now).total_seconds()
            return max(1, min(time_delta, default_interval))

        return default_interval

    def _start_process_monitor(self):
        """Start the process monitor thread — does nothing in process-replacement mode"""
        logging.info("ℹ️ Process monitoring disabled (using PID file for process management)")
        return

    def _process_monitor_loop(self):
        """Process monitor loop — does nothing in multi-instance mode"""
        pass

# Create the global scheduler instance
task_scheduler = TaskScheduler()
