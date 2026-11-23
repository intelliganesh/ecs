"""Read-only dashboard listing, including jobs that need to be re-enabled.

The legacy query 42 remains unchanged for its enabled-only consumers. Listing
visibility is separate from scheduler eligibility and never changes job state.
"""

from sqlalchemy import text


READ_ALL_JOBS = text("""
SELECT j.jobid, j.jobdesc, j.jobfilename, j.jobstatus, j.joblastmodified,
       CASE WHEN j.joblastrun > ISNULL(h.Job_Last_Trigger_Date, '19000101')
            THEN j.joblastrun ELSE h.Job_Last_Trigger_Date END AS joblastrun,
       j.filetype, j.ismerge, j.isEnabled,
       s.startDateTime, s.ScheduleType, s.ScheduleWeek,
       s.schedule_hr, s.schedule_min, s.schedules_session,
       h.Job_Last_Status, h.Job_Last_Message
FROM dbo.rjob AS j
LEFT JOIN dbo.rjob_schedule_info AS s ON s.jobid = j.jobid
OUTER APPLY (
    SELECT TOP (1) Job_Last_Trigger_Date, Job_Last_Status, Job_Last_Message
    FROM dbo.rjob_history AS history
    WHERE history.Job_Id = j.jobid
    ORDER BY COALESCE(history.Job_Update_Date, history.Job_Create_Date) DESC,
             history.Job_Last_Trigger_Date DESC
) AS h
ORDER BY j.isEnabled DESC, j.jobid DESC
""")
