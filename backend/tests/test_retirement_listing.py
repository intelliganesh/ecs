from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

from app.retirement_listing import READ_ALL_JOBS
from app.routers import retirement_builder as rb


class RetirementListingTests(TestCase):
    def test_enabled_disabled_and_unscheduled_jobs_are_listed_without_losing_saved_schedules(self):
        common = {"jobfilename": "Synthetic", "filetype": ",", "jobdesc": "",
                  "startDateTime": datetime(2026, 11, 1), "ScheduleType": "W", "ScheduleWeek": 4,
                  "schedule_hr": 9, "schedule_min": 5, "schedules_session": "PM",
                  "joblastrun": datetime(2026, 11, 2), "Job_Last_Status": "Success"}
        rows = [
            {**common, "jobid": 1, "isEnabled": True},
            {**common, "jobid": 2, "isEnabled": False},
            {**common, "jobid": 3, "isEnabled": None, "startDateTime": None,
             "schedule_hr": None, "schedule_min": None, "schedules_session": None},
        ]
        connection = Mock()
        connection.execute.return_value.mappings.return_value.all.return_value = rows
        with patch.object(rb.engine, "connect") as connect, patch.object(rb, "_file_formats", return_value={"CSV": ","}):
            connect.return_value.__enter__.return_value = connection
            jobs = rb.list_retirement_builder_jobs()
        connection.execute.assert_called_once_with(READ_ALL_JOBS)
        self.assertEqual([job["id"] for job in jobs], [1, 2, 3])
        self.assertTrue(jobs[0]["general"]["enable"])
        self.assertFalse(jobs[1]["general"]["enable"])
        self.assertFalse(jobs[2]["general"]["enable"])
        self.assertEqual(jobs[1]["runtime"], "9:05 PM")
        self.assertEqual(jobs[1]["schedule"]["buildFrequency"], "Weekly")
        self.assertEqual(jobs[1]["schedule"]["week"], "Thursday")
        self.assertEqual(jobs[1]["joblastrun"], common["joblastrun"])
        self.assertEqual(jobs[2]["runtime"], "")
        self.assertIsNone(jobs[2]["schedule"]["startDate"])

    def test_disabled_sunday_schedule_and_midnight_are_not_treated_as_missing_values(self):
        job = rb._api_job_from_row({
            "jobid": 2, "isEnabled": False, "ScheduleWeek": 0, "ScheduleType": "D",
            "schedule_hr": 12, "schedule_min": 0, "schedules_session": "AM",
        })
        self.assertEqual(job["runtime"], "12:00 AM")
        self.assertEqual(job["schedule"]["week"], "Sunday")
        self.assertEqual(job["schedule"]["buildFrequency"], "Daily")
