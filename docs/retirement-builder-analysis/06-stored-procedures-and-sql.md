# Stored procedures and SQL evidence

## What was confirmed

A SELECT-only connection succeeded. The configured application procedure is **`dbo.usp_CompanyPayrollReport`**. `OBJECT_DEFINITION` was visible, and its definition matched migration 012 after whitespace and CREATE/ALTER declaration normalization. Its live parameters are `@jobid int`, `@start_date date`, `@end_date date`. No procedure was executed in this investigation. [Database evidence](evidence/read-only-database.json).

Count: **1 application stored procedure**, plus the SQL Server system helper **`sys.sp_executesql`** called inside it. The older `dbo.ufn_CompanyPayrollRecordQueries` is a function in migration 009; migration 011 drops it. The current source uses JSON H/D/T templates and does not call that function. Its actual absence from the live database was **NOT VERIFIED**. [backend/migrations/009_payroll_record_queries.sql:1](/Users/apple/Desktop/ESC/backend/migrations/009_payroll_record_queries.sql:1), [backend/migrations/011_inline_payroll_record_queries.sql:47](/Users/apple/Desktop/ESC/backend/migrations/011_inline_payroll_record_queries.sql:47), [backend/app/payroll_source.py:84](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:84).

There are **32 distinct application SQL definitions/templates in the traced flow**: 15 active query.brl batches, 13 direct Python SQL constants, 1 generated payroll-call wrapper, and 3 H/D/T SELECT templates. This counts a batch as one unit, not every SQL keyword/subquery. The combined edit-read batch reuses eight reads and is not counted again. The procedure body is explained separately, not added a second time. Auxiliary health `SELECT 1` and migration DDL/seed statements are excluded. All 32 units appear below. The repository's many unrelated query.brl IDs are not all used by Retirement Builder. [backend/app/routers/retirement_builder.py:218](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:218), [backend/app/routers/retirement_builder.py:235](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:235), [backend/app/payroll_source.py:44](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:44), [backend/app/retirement_results.py:76](/Users/apple/Desktop/ESC/backend/app/retirement_results.py:76), [backend/app/payroll_source.py:132](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:132).

## Application procedure: dbo.usp_CompanyPayrollReport

**Call site:** `load_payroll_source` → raw cursor `execute(payroll_report_query(job, for_run=True), job.id, date_range.start, date_range.end)` [backend/app/payroll_source.py:198](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:198). `_payroll_procedure_name` reads the validated configured name, schema-qualified and bracketed. [backend/app/payroll_source.py:65](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:65).

| Input | Actual source | Meaning |
|---|---|---|
| @jobid | Saved job database ID selected on Dashboard, or scheduled job ID | Read approved H/D/T SQL from rjob_query for that job; legacy PAYROLL can use built-ins |
| @start_date | Run dialog start_date; omitted/null becomes 1900-01-01; scheduler uses sentinel | Inclusive lower bound on date cast of payroll_month |
| @end_date | Run dialog end_date; omitted/null becomes 1900-01-01; scheduler uses sentinel | Inclusive upper bound on same source date |

**Outputs:** one result set containing `[Record Sequence]`, `[Record Type]`, `[Company Name]`, `[Pay Date]`, `[Employee Count]`, `[Net Salary Total]`. Sequence is 1 for H, 2 for D, 3 for T. H has blank date text converted through the common result shape and zeros for count/total. The application wrapper projects requested columns, makes Header Pay Date NULL, orders records, and optionally appends Client ID after a separate company lookup. [backend/app/payroll_source.py:164](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:164), [backend/app/payroll_source.py:202](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:202).

**Persistent tables read:** `dbo.rjob_query`, `dbo.companies`, `dbo.employees`, `dbo.payroll`. Joins: employees.company_id=companies.id; payroll.employee_id=employees.id. D/T group by company_name,payroll_month. The feature's procedure does not insert/update/delete persistent data; `INSERT INTO @templates`, `@records`, `@payroll` are temporary table-variable operations. Run as a whole still writes history/output/results outside this procedure. [backend/migrations/012_payroll_report_date_range.sql:9](/Users/apple/Desktop/ESC/backend/migrations/012_payroll_report_date_range.sql:9), [backend/app/routers/retirement_builder.py:1154](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1154).

### Definition explained section by section

| Definition lines | Simple meaning |
|---|---|
| 1–7 | Declare three inputs; disable affected-row chatter with NOCOUNT |
| 9–13 | Establish server-approved Header, Detail, Trailer SELECT texts; D/T aggregate COUNT(*) and SUM(net_salary) |
| 15–25 | Load built-ins for no job ID or legacy PAYROLL-only configuration; otherwise load saved H/D/T for this job |
| 27–36 | Require exactly three rows and a matching SHA-256 hash for every approved type. Saved arbitrary query text is rejected with SQL error 50005 |
| 38–42 | Turn NULL into open-date sentinel; reject reversed bounded range with SQL error 50006 |
| 44–50 | Build report CTE by UNION ALL H, D, T, preserving duplicate records rather than deduplicating |
| 51–56 | Keep D/T within inclusive date bounds; open side does not restrict |
| 57–64 | Keep H for companies with dated records, or all headers when completely unbounded; union dated D/T; sort sequence, company descending, date |
| 65–66 | Execute constructed SELECT through sys.sp_executesql with bound dates |

Full current repository definition (confirmed matching installed definition):

```sql
CREATE OR ALTER PROCEDURE dbo.usp_CompanyPayrollReport
    @jobid int = NULL,
    @start_date date = '19000101',
    @end_date date = '19000101'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @templates TABLE (recttype varchar(10), [Query] varchar(max));
    INSERT INTO @templates (recttype, [Query]) VALUES
        ('H', '/* company payroll */ SELECT 1, ''H'' AS RECTYPE, c.company_name, '''', 0, 0 FROM dbo.companies AS c'),
        ('D', '/* company payroll */ SELECT 2, ''D'', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month'),
        ('T', '/* company payroll */ SELECT 3, ''T'', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month');

    DECLARE @records TABLE (recttype varchar(10), [Query] varchar(max));
    -- A saved legacy PAYROLL job used the built-in templates before H/D/T rows existed.
    IF @jobid IS NULL OR (
        EXISTS (SELECT 1 FROM dbo.rjob_query WHERE jobid = @jobid AND recttype = 'PAYROLL')
        AND NOT EXISTS (SELECT 1 FROM dbo.rjob_query WHERE jobid = @jobid AND recttype IN ('H', 'D', 'T'))
    )
        INSERT INTO @records SELECT recttype, [Query] FROM @templates;
    ELSE
        INSERT INTO @records
        SELECT recttype, [Query] FROM dbo.rjob_query
        WHERE jobid = @jobid AND recttype IN ('H', 'D', 'T');

    -- Only execute SQL matching the server's approved SELECTs for each record type.
    IF (SELECT COUNT(*) FROM @records) <> 3 OR EXISTS (
        SELECT 1 FROM @templates AS expected
        WHERE NOT EXISTS (
            SELECT 1 FROM @records AS saved
            WHERE saved.recttype = expected.recttype
              AND HASHBYTES('SHA2_256', saved.[Query]) = HASHBYTES('SHA2_256', expected.[Query])
        )
    )
        THROW 50005, 'This payroll job needs one approved H, D, and T query.', 1;

    DECLARE @unbounded date = '19000101';
    SET @start_date = COALESCE(@start_date, @unbounded);
    SET @end_date = COALESCE(@end_date, @unbounded);
    IF @start_date <> @unbounded AND @end_date <> @unbounded AND @start_date > @end_date
        THROW 50006, 'Start Date must be on or before End Date.', 1;

    -- The saved H/D/T texts keep their original hashes and result shape.
    DECLARE @sql nvarchar(max) =
        N';WITH report ([Record Sequence], [Record Type], [Company Name], [Pay Date],
                       [Employee Count], [Net Salary Total]) AS ('
        + (SELECT [Query] FROM @records WHERE recttype = 'H') + N' UNION ALL '
        + (SELECT [Query] FROM @records WHERE recttype = 'D') + N' UNION ALL '
        + (SELECT [Query] FROM @records WHERE recttype = 'T') + N'),
        dated AS (
            SELECT * FROM report
            WHERE [Record Type] IN (''D'', ''T'')
              AND (@start_date = @unbounded OR CAST([Pay Date] AS date) >= @start_date)
              AND (@end_date = @unbounded OR CAST([Pay Date] AS date) <= @end_date)
        )
        SELECT * FROM report AS header
        WHERE header.[Record Type] = ''H''
          AND ((@start_date = @unbounded AND @end_date = @unbounded) OR EXISTS (
                SELECT 1 FROM dated WHERE [Company Name] = header.[Company Name]
          ))
        UNION ALL
        SELECT * FROM dated
        ORDER BY [Record Sequence], [Company Name] DESC, [Pay Date];';
    EXEC sys.sp_executesql @sql, N'@start_date date, @end_date date, @unbounded date',
        @start_date = @start_date, @end_date = @end_date, @unbounded = @unbounded;
END;
GO
```

No `Conditions` or `Sort_Order` is concatenated by this procedure. Those are parsed into Python fileSettings and applied after payroll retrieval. The approved H/D/T query text is executed here, whereas saved condition/sort text is interpreted by application helpers. [backend/app/payroll_source.py:112](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:112), [backend/app/retirement_results.py:438](/Users/apple/Desktop/ESC/backend/app/retirement_results.py:438).

No rows: if there are no matching bounded payroll records, the renderer returns `[]` and the run records successful no-output completion; an unbounded empty/missing required layout can instead fail its record-type checks. Payroll cursor with **no result set** is an error, distinct from an empty valid result set. [backend/app/payroll_source.py:199](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:199), [backend/app/retirement_results.py:482](/Users/apple/Desktop/ESC/backend/app/retirement_results.py:482).

### System helper sys.sp_executesql

Called from migration 012 lines 65–66; `@sql` contains only approved H/D/T SELECT text plus the fixed CTE wrapper; parameter-definition string declares three dates and values bind normalized range dates/sentinel. Its output is the SELECT above. Tables and read-only business behavior are inherited from that SQL. SQL Server's own helper implementation is not in this repository and was not inspected. [backend/migrations/012_payroll_report_date_range.sql:65](/Users/apple/Desktop/ESC/backend/migrations/012_payroll_report_date_range.sql:65).

## All SQL batches loaded from query.brl and direct constants

`_prepared_query` converts legacy `@parameter` markers to SQLAlchemy named binds, including markers surrounded by single quotes. It does not interpolate the UI values into SQL. `_execute_identity_query` compiles bind order and reads cursor result sets until it finds a positive identity. Raw query.brl excerpts below therefore show legacy markers, while runtime executes prepared bindings. [backend/app/routers/retirement_builder.py:453](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:453), [backend/app/routers/retirement_builder.py:580](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:580).

### SQL-30: query.brl sqlid="30"

Read mapping metadata. No parameters. Outputs mapping_column, mapping_column_desc, mapping_column_dt. No WHERE/join; every row can become a label/type entry. Empty table → empty mapping options. Called by options, save mapping normalization and report source-label setup.

Definition: [backend/query.brl:456](/Users/apple/Desktop/ESC/backend/query.brl:456). Parameters: none.

```sql
SELECT [mapping_column]
      ,[mapping_column_desc]
      ,[mapping_column_dt]
  FROM  [dbo].[rjob_mapping_column]
```

### SQL-31: query.brl sqlid="31"

Insert one queryConfiguration row: @jobid from saved identity/path; @recttype H/D/T for generated payroll templates (or CSV_SORT/retained legacy rows); @Query from approved JSON template or preserved query configuration; @conditionalStmt from saved rule clauses; @sortOrder from formatted sort settings. No result set. Table rjob_query. Not a stored procedure execution: it saves SQL text.

Definition: [backend/query.brl:466](/Users/apple/Desktop/ESC/backend/query.brl:466). Parameters: @Query, @conditionalStmt, @jobid, @recttype, @sortOrder.

```sql
INSERT INTO [dbo].[rjob_query]
           ([jobid]
           ,[recttype]
           ,[Query]
           ,Conditions
           ,[Sort_Order])
     VALUES
           (@jobid,
           '@recttype',
           '@Query',
           '@conditionalStmt',
           '@sortOrder')
```

### SQL-32: query.brl sqlid="32"

Read file-type lookup, no parameters. SELECT * includes filetyp and delimiter consumed by code. Used by options, list, edit, save validation and run delimiter resolution. Empty table → no file-format choices and new saves/runs reject unsupported formats.

Definition: [backend/query.brl:482](/Users/apple/Desktop/ESC/backend/query.brl:482). Parameters: none.

```sql
select * from [dbo].[rjob_file_typ]
```

### SQL-35: query.brl sqlid="35"

Insert one mapping into rjob_file_detail. @jobid from identity/path; @jobclientcolumn=field; @jobfieldmapping=resolved mapping key; @jobdefaultvalue=defaultValue; @jobformat=format; @jobrectype=H/D/T; @startposition/startPosition and @field_len/length parsed integers; @datasetNo always 1; @colSeqNo row index from 1. No result set.

Definition: [backend/query.brl:504](/Users/apple/Desktop/ESC/backend/query.brl:504). Parameters: @colSeqNo, @datasetNo, @field_len, @jobclientcolumn, @jobdefaultvalue, @jobfieldmapping, @jobformat, @jobid, @jobrectype, @startposition.

```sql
INSERT INTO [dbo].[rjob_file_detail]
           ([jobid]
           ,[jobclientcolumn]
           ,[jobfieldmapping]
           ,[jobdefaultvalue]
           ,[jobformat]
           ,[jobrectype]
           ,[startposition]
           ,[field_len]
           ,[DataSetNo]
           ,[ColSeqNo])
     VALUES
           (@jobid
           ,'@jobclientcolumn'
           ,'@jobfieldmapping'
           ,'@jobdefaultvalue'
           ,'@jobformat'
           ,'@jobrectype'
           ,@startposition
           ,@field_len,@datasetNo,@colSeqNo)
```

### SQL-36: query.brl sqlid="36"

Insert parent into rjob. Inputs from general/subscriptions/mapping: @jobdesc, @jobfilename, @jobstatus fixed Active, @filetype resolved delimiter, @ismerge, @mergeemail combined addresses, @includeHRecord, @fileNameFormat normalized code, @isEnabled, @StoreResult, @enddate None. GETDATE stamps modified and last-run columns. SELECT SCOPE_IDENTITY returns the new ID used for child inserts. Failure to read a positive identity becomes save error.

Definition: [backend/query.brl:529](/Users/apple/Desktop/ESC/backend/query.brl:529). Parameters: @StoreResult, @enddate, @fileNameFormat, @filetype, @includeHRecord, @isEnabled, @ismerge, @jobdesc, @jobfilename, @jobstatus, @mergeemail.

```sql
INSERT INTO [dbo].[rjob]
           ([jobdesc]
           ,[jobfilename]
           ,[jobstatus]
           ,[joblastmodified]
           ,[joblastrun],[filetype],[ismerge],[mergeemail],[includeHeader],[FileNameFormat],[isEnabled],[StoreResults],[enddate])
     VALUES
           ('@jobdesc',
			'@jobfilename',
			'@jobstatus',
			GETDATE(),
			GETDATE(),'@filetype',@ismerge, '@mergeemail',@includeHRecord,'@fileNameFormat','@isEnabled','@StoreResult','@enddate')
      SELECT SCOPE_IDENTITY()
```

### SQL-37: query.brl sqlid="37"

Insert one subscription: @jobid identity/path, @jobclientid positive companyId or parsed CSV client ID, @jobemailind row email. Table rjob_client_detail. Blank email allowed. No SELECT result.

Definition: [backend/query.brl:550](/Users/apple/Desktop/ESC/backend/query.brl:550). Parameters: @jobclientid, @jobemailind, @jobid.

```sql
INSERT INTO [dbo].[rjob_client_detail]
  ([jobid]
  ,[jobclientid]
  ,[jobemailind])
  VALUES
  (@jobid
  ,@jobclientid
  ,'@jobemailind')
```

### SQL-38: query.brl sqlid="38"

Insert schedule into rjob_schedule_info. @jobid parent ID; @jobName fileName; @startDateTime date/time conversion or None; @dayInterval/@weekInterval both 0; @rbJobTypeChk frequency label; @ScheduleType D/W/B/M; @MonthlyWeekNo and @MonthlyDate blank; @ScheduleWeek Sunday-based index; @schedule_hr/@schedule_min parsed strings; @schedule_session AM/PM. Null date means manual-only. No result set.

Definition: [backend/query.brl:567](/Users/apple/Desktop/ESC/backend/query.brl:567). Parameters: @MonthlyDate, @MonthlyWeekNo, @ScheduleType, @ScheduleWeek, @dayInterval, @jobName, @jobid, @rbJobTypeChk, @schedule_hr, @schedule_min, @schedule_session, @startDateTime, @weekInterval.

```sql
INSERT INTO [dbo].[rjob_schedule_info]
  ([jobid]
  ,[jobName]
  ,[startDateTime]
  ,[dayInterval]
  ,[weekInterval]
  ,[rbJobTypeChk]
  ,[ScheduleType]
  ,[MonthlyWeekNo]
  ,[ScheduleWeek],[MonthlyDate],
   [schedule_hr]
      ,[schedule_min]
      ,[schedules_session]
  )
  VALUES
  (@jobid
  ,'@jobName'
  ,CONVERT(DATETIME, '@startDateTime')
  ,@dayInterval
  ,@weekInterval
  ,'@rbJobTypeChk'
  ,'@ScheduleType'
  ,'@MonthlyWeekNo'
  ,'@ScheduleWeek','@MonthlyDate',
  '@schedule_hr','@schedule_min','@schedule_session'
  
  )
```

### SQL-42: query.brl sqlid="42"

Read dashboard. Inner join rjob_schedule_info on job ID excludes parents without schedule rows; left join history on job ID; left join a GLOBAL TOP 1 history_details subquery, not latest per job. WHERE isEnabled=1. Returns parent data, day/time/frequency strings, activity, history status/message, formatted range. Backend suppresses initial last-run date if no status and overlays in-process running status. Empty → dashboard no matching records. Multiple history/schedule rows can multiply a parent; no DISTINCT or grouping prevents that.

Definition: [backend/query.brl:693](/Users/apple/Desktop/ESC/backend/query.brl:693). Parameters: none.

```sql
SELECT RJ.jobid
      ,[jobdesc]
      ,[jobfilename]
      ,[jobstatus]
      ,[joblastmodified]
      ,case when (case when joblastrun> ISNULL(job_last_trigger_Date,'01/01/1900') then joblastrun
	  else Job_Last_Trigger_Date end)='01/01/1900' then '' else (case when joblastrun> ISNULL(job_last_trigger_Date,'01/01/1900') then joblastrun
	  else Job_Last_Trigger_Date end) end
	  joblastrun
	  ,case when RSI.ScheduleWeek =0 then 'Sunday'
			when RSI.ScheduleWeek=1 then 'Monday'
			when RSI.ScheduleWeek=2 then 'Tuesday'
			when RSI.ScheduleWeek=3 then 'Wednesday'
			when RSI.ScheduleWeek=4 then 'Thursday'
			when RSI.ScheduleWeek=5 then 'Friday'
			when RSI.ScheduleWeek=6 then 'Saturday' 
			else '' end as runday
	  ,CAST(RSI.schedule_hr as varchar)+':'+case when schedule_min=0 then '00' else cast(schedule_min as varchar) end +' '+RSI.schedules_session runtime
	  ,case when RSI.ScheduleType='D' then 'Daily'
			when RSI.ScheduleType='W' then 'Weekly'
			when RSI.ScheduleType='B' then 'Bi-Weekly'
			when RSI.ScheduleType='M' then 'Monthly'
			when RSI.ScheduleType='MD' then 'Monthly'
			else '' end ScheduleType
      ,[filetype]
      ,[ismerge]
      ,[isEnabled]
	  ,case when ISNULL(isEnabled,0)=1 then 'Yes' else 'No' end as IsActive
	  ,RH.Job_Last_Status,
	  RH.Job_Last_Message,
	  CONVERT(VARCHAR,RHD.START_DATE,101) as Start_Date,
   CONVERT(VARCHAR,RHD.END_DATE,101) as End_Date
  FROM [dbo].[rjob] RJ
  inner join [dbo].[rjob_schedule_info] RSI on RSI.jobid=RJ.jobid
  left join [dbo].[rjob_history] RH on RH.Job_Id=RJ.jobid
  left join (Select top 1 [Id]
      ,[Job_Id]
      ,[Flag]
      ,[Start_Date]
      ,[End_Date]
      ,[Pay_Date]
	  from [dbo].rjob_history_details 
	  order by Id desc) RHD ON RHD.Job_Id=RJ.jobid 
     where isEnabled=1
	order by isEnabled desc
```

### SQL-43: query.brl sqlid="43"

Read CSV client options from prism.export.Client_Details. Current SQL is NOT the commented-out dbo.Client SELECT. Excludes Client_Status_Code=T; NULL status also does not satisfy !=T. Cast Client_ID to decimal and combine ID/name into client_name. Ordered by ID then label. No parameters. Backend filters valid positive IDs and deduplicates first label. Empty → no catalog options but custom ID entry remains; SQL error →503.

Definition: [backend/query.brl:743](/Users/apple/Desktop/ESC/backend/query.brl:743). Parameters: none.

```sql
--SELECT [id]
 -- ,[client_name]
  --,[client_email]
  --FROM [dbo].[Client]
  select cast(Client_ID as decimal) as id,CAST(Client_ID as varchar)+' - '+Client_DBA_Name as client_name from prism.export.Client_Details
where Client_Status_Code!='T'
order by 1,2
```

### SQL-44: query.brl sqlid="44"

DELETE batch for one @jobid path parameter. Clears rjob_query, rjob_client_detail, rjob_file_detail, rjob_schedule_info, rjob_file_sorting_details and rjob_file_condition_details. Only called inside PUT transaction before recreating effective details. Does not delete rjob, results or history. Six statements count as one source-defined SQL batch in the total.

Definition: [backend/query.brl:755](/Users/apple/Desktop/ESC/backend/query.brl:755). Parameters: @jobid.

```sql
DELETE FROM [dbo].[rjob_query] WHERE jobid=@jobid
  DELETE FROM [dbo].[rjob_client_detail] WHERE jobid=@jobid
  DELETE FROM [dbo].[rjob_file_detail] WHERE jobid=@jobid
  DELETE FROM [dbo].[rjob_schedule_info] WHERE jobid=@jobid
  DELETE FROM [dbo].[rjob_file_sorting_details] where job_id=@jobid
  DELETE FROM [dbo].[rjob_file_condition_details] where job_id=@jobid
```

### SQL-45: query.brl sqlid="45"

UPDATE parent WHERE jobid=@jobid; parameters come from merged effective general/mapping/subscriptions payload, as for query36 except no enddate argument. Updates modified AND joblastrun to GETDATE even though no report was run; displayed last-run can therefore move on edit if a history status already exists. No result set.

Definition: [backend/query.brl:765](/Users/apple/Desktop/ESC/backend/query.brl:765). Parameters: @StoreResult, @fileNameFormat, @filetype, @includeHRecord, @isEnabled, @ismerge, @jobdesc, @jobfilename, @jobid, @jobstatus, @mergeemail.

```sql
UPDATE [dbo].[rjob]
   SET [jobdesc] = '@jobdesc'
      ,[jobfilename] = '@jobfilename'
      ,[jobstatus] = '@jobstatus'
      ,[joblastmodified] = GETDATE()
      ,[joblastrun] = GETDATE()
      ,[filetype] = '@filetype'
      ,[ismerge] = @ismerge 
      ,[mergeemail]='@mergeemail'
      ,[FileNameFormat]='@fileNameFormat'
	  ,[includeHeader]=@includeHRecord
    ,[isEnabled]='@isEnabled'
      ,[StoreResults] ='@StoreResult'
 WHERE [jobid]=@jobid
```

### SQL-52: query.brl sqlid="52"

UPDATE rjob_history WHERE job_id=@JOB_ID. @JOB_ID saved job ID, @STATUS Success/Failed, @STAT_MSG generation/failure message. Updates trigger/update date and status. No insert if absent: _record_run checks rowcount and uses INSERT_RUN_HISTORY if zero. All matching history rows update, not a specific run UUID.

Definition: [backend/query.brl:640](/Users/apple/Desktop/ESC/backend/query.brl:640). Parameters: @JOB_ID, @STATUS, @STAT_MSG.

```sql
UPDATE [dbo].[rjob_history]
      SET [Job_Last_Trigger_Date]=GETDATE(),
      [Job_Last_Status]='@STATUS',
      [Job_Last_Message]='@STAT_MSG',
      [Job_Update_Date]=GETDATE()
    WHERE job_id=@JOB_ID
```

### SQL-53: query.brl sqlid="53"

Read format metadata from rjobformat. Returns jobformat, concatenated jobdesc label, jobformattype. No params/WHERE. Backend filters recognized text/date/number/phone/email/ssn/all buckets; current output-name categories are excluded, so live Format choices empty.

Definition: [backend/query.brl:651](/Users/apple/Desktop/ESC/backend/query.brl:651). Parameters: none.

```sql
SELECT [jobformat],[jobformat]+' - '+[jobformat_desc] as jobdesc,[jobformattype] FROM [dbo].[rjobformat]
```

### SQL-54: query.brl sqlid="54"

Insert sort detail: @jobid saved ID, @order compact positive sequential priority starting at 1, @mapping source label stripped. Table rjob_file_sorting_details stores no direction column. Direction survives separately in rjob_query.Sort_Order. No result set.

Definition: [backend/query.brl:657](/Users/apple/Desktop/ESC/backend/query.brl:657). Parameters: @jobid, @mapping, @order.

```sql
INSERT INTO [dbo].[rjob_file_sorting_details]
  (
	job_id
    ,sort_order
    ,mapping_column
  )
  VALUES(
  @jobid,
  @order,
 '@mapping'
  )
```

### SQL-55: query.brl sqlid="55"

Insert filter: @jobid saved ID, @mapping rule.mappingColumn, @Symbol comparison or date:comparison, @val rounded numeric or compact YYYYMMDD. Table rjob_file_condition_details. No result set. Dates encoded to fit numeric column and decoded on read.

Definition: [backend/query.brl:672](/Users/apple/Desktop/ESC/backend/query.brl:672). Parameters: @Symbol, @jobid, @mapping, @val.

```sql
INSERT INTO [dbo].[rjob_file_condition_details]
  (
	    job_id
      ,mapping_column
      ,condition_symbol
      ,condition_value
  )
  VALUES(
  @jobid,
  '@mapping',
 '@Symbol',
 '@val'
  )
```

### READ_JOB

Read one parent by :jobid; None → detail 404/run 404. Selects StoreResults, includeHeader, FileNameFormat, enable and parent metadata.

Definition: [backend/app/routers/retirement_builder.py:235](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:235).

```sql
SELECT jobid, jobdesc, jobfilename, jobstatus, joblastmodified, joblastrun,
       filetype, ismerge, mergeemail, includeHeader, FileNameFormat,
       isEnabled, StoreResults, enddate
FROM dbo.rjob
WHERE jobid = :jobid
```

### READ_SCHEDULE

Read schedule by :jobid. Supplies form date/frequency/time, and scheduler revalidation. Existing invalid/missing schedule values can fail model reconstruction; there is no universal empty-value repair.

Definition: [backend/app/routers/retirement_builder.py:242](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:242).

```sql
SELECT jobid, jobName, startDateTime, dayInterval, weekInterval,
       rbJobTypeChk, ScheduleType, MonthlyWeekNo, ScheduleWeek, MonthlyDate,
       schedule_hr, schedule_min, schedules_session
FROM dbo.rjob_schedule_info
WHERE jobid = :jobid
```

### READ_ENABLED_SCHEDULES

Read enabled jobs joined to non-null startDateTime schedules, ordered by job ID. Used to hide default schedule labels for manual jobs and by scheduler scanning. Empty → nothing scheduled.

Definition: [backend/app/routers/retirement_builder.py:249](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:249).

```sql
SELECT j.jobid, s.startDateTime, s.ScheduleType, s.ScheduleWeek, s.MonthlyDate,
       s.schedule_hr, s.schedule_min, s.schedules_session
FROM dbo.rjob AS j
JOIN dbo.rjob_schedule_info AS s ON j.jobid = s.jobid
WHERE j.isEnabled = 1 AND s.startDateTime IS NOT NULL
ORDER BY j.jobid
```

### READ_MAPPINGS

Read mappings by :jobid ordered DataSetNo,ColSeqNo. Output names/source/default/format/type/position/length reconstruct rows. Empty → no mappings; UI/run require at least one.

Definition: [backend/app/routers/retirement_builder.py:257](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:257).

```sql
SELECT jobid, jobclientcolumn, jobfieldmapping, jobdefaultvalue, jobformat,
       jobrectype, startposition, field_len, DataSetNo, ColSeqNo
FROM dbo.rjob_file_detail
WHERE jobid = :jobid
ORDER BY DataSetNo, ColSeqNo
```

### READ_SUBSCRIPTIONS

Read positive/legacy encoded recipient IDs and emails by :jobid; payroll source determines ID namespace. Empty → no subscriptions, valid.

Definition: [backend/app/routers/retirement_builder.py:264](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:264).

```sql
SELECT jobid, jobclientid, jobemailind
FROM dbo.rjob_client_detail
WHERE jobid = :jobid
ORDER BY jobclientid
```

### READ_SORTING

Read sort priorities and mapping columns by :jobid ordered sort_order. Older negative order encodes DESC as -stored-1 priority. Saved query Sort_Order takes precedence when available. Empty → no fallback sorts.

Definition: [backend/app/routers/retirement_builder.py:270](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:270).

```sql
SELECT job_id, sort_order, mapping_column
FROM dbo.rjob_file_sorting_details
WHERE job_id = :jobid
ORDER BY sort_order
```

### READ_CONDITIONS

Read mapping/operator/value by :jobid, ordered mapping_column. _condition_from_db decodes date:prefix and compact date. Empty → no detail filters.

Definition: [backend/app/routers/retirement_builder.py:276](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:276).

```sql
SELECT job_id, mapping_column, condition_symbol, condition_value
FROM dbo.rjob_file_condition_details
WHERE job_id = :jobid
ORDER BY mapping_column
```

### READ_QUERY_CONFIGURATION

Read saved query texts/conditions/sort by :jobid ordered Sort_Order,recttype. Recognized PAYROLL or marked H/D/T determines source. Missing/partial approved H/D/T can block run.

Definition: [backend/app/routers/retirement_builder.py:282](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:282).

```sql
SELECT jobid, recttype, Query, Conditions, Sort_Order
FROM dbo.rjob_query
WHERE jobid = :jobid
ORDER BY Sort_Order, recttype
```

### LOCK_RUN_JOB

Read one ID with UPDLOCK,HOLDLOCK by :jobid inside transaction; serializes report attempts until commit. It is a lock-taking read, not a row update. Missing ID →404 for manual run, skip for scheduler.

Definition: [backend/app/routers/retirement_builder.py:295](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:295).

```sql
SELECT jobid FROM dbo.rjob WITH (UPDLOCK, HOLDLOCK) WHERE jobid = :jobid
```

### INSERT_RUN_HISTORY

Insert history only if query52 rowcount=0. :jobid saved ID, :run_status Success/Failed, :message bounded run message; GETDATE for timestamps. No output consumed.

Definition: [backend/app/routers/retirement_builder.py:296](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:296).

```sql
INSERT INTO dbo.rjob_history
    (Job_Id, Job_Create_Date, Job_Last_Trigger_Date, Job_Last_Status, Job_Last_Message, Job_Update_Date)
VALUES (:jobid, GETDATE(), GETDATE(), :run_status, :message, GETDATE())
```

### INSERT_RUN_DATES

Insert every recorded attempt: :jobid, :flag A manual or S scheduled, :start_date/:end_date normalized requested dates (1900 sentinel when open). History_details has no run UUID correlation in this insert.

Definition: [backend/app/routers/retirement_builder.py:301](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:301).

```sql
INSERT INTO dbo.rjob_history_details (Job_Id, Flag, Start_Date, End_Date)
VALUES (:jobid, :flag, :start_date, :end_date)
```

### READ_PAYROLL_COMPANY_IDS

Read companies grouped by company_name with HOLDLOCK; COUNT_BIG=1 →MIN(id), duplicate name →NULL. Options drop NULL/nonpositive IDs. Run requiring company identity rejects unmatched/ambiguous names. No parameters. Not a company-data update.

Definition: [backend/app/payroll_source.py:44](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:44).

```sql
SELECT company_name, CASE WHEN COUNT_BIG(*) = 1 THEN MIN(id) END
FROM dbo.companies WITH (HOLDLOCK)
GROUP BY company_name
```

### INSERT_RESULT

Insert mapped report records only if Store Results enabled. Each row receives generated UUID :run_id, :job_id, 1-based :row_number, H/D/T :record_type, JSON output dictionary :row_values. No read result consumed; store_results returns len(rows).

Definition: [backend/app/retirement_results.py:76](/Users/apple/Desktop/ESC/backend/app/retirement_results.py:76).

```sql
INSERT INTO dbo.rjob_result (run_id, job_id, row_number, record_type, row_values)
    VALUES (:run_id, :job_id, :row_number, :record_type, :row_values)
```

## Generated payroll wrapper: SQL unit 29

Defined in `payroll_report_query` [backend/app/payroll_source.py:132](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:132). Example below uses all five report columns and all three configured record types; actual projection/type list depends on job mappings, naming and rules. The procedure name is the confirmed configured name; `?` arguments are bound job ID/start/end, not string interpolation.

```sql
DECLARE @payroll TABLE (
  [Record Sequence] int, [Record Type] varchar(1),
  [Company Name] varchar(120), [Pay Date] datetime,
  [Employee Count] int, [Net Salary Total] numeric(38,2)
);
INSERT INTO @payroll EXEC [dbo].[usp_CompanyPayrollReport]
  @jobid = ?, @start_date = ?, @end_date = ?;
SELECT TOP (10001)
  [Record Type], [Company Name],
  CASE WHEN [Record Type] = 'H' THEN NULL ELSE [Pay Date] END AS [Pay Date],
  [Employee Count], [Net Salary Total]
FROM @payroll
WHERE [Record Type] IN ('D', 'H', 'T')
ORDER BY [Record Sequence], [Company Name] DESC, [Pay Date];
```

The 10,001st row detects exceeding the 10,000 source-row limit. Without a payroll source (CSV override or saved CSV), this wrapper and SP are not called. Data is converted to a UTF-8 CSV in memory for the common renderer. It is not a physical payroll staging table. [backend/app/payroll_source.py:194](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:194), [backend/app/routers/retirement_builder.py:1214](/Users/apple/Desktop/ESC/backend/app/routers/retirement_builder.py:1214).

## H/D/T templates: SQL units 30–32

Exact source: [backend/config/payroll_record_queries.json:1](/Users/apple/Desktop/ESC/backend/config/payroll_record_queries.json:1). These are saved by query31 on Finish, validated against approved texts by the procedure, and executed inside the SP. H reads companies; D and T read companies/employees/payroll and return the same grouped count and net-salary sum with different sequence/type literals. No inputs are inserted into their SQL strings.

```sql
/* company payroll */ SELECT 1, 'H' AS RECTYPE, c.company_name, '', 0, 0 FROM dbo.companies AS c;
/* company payroll */ SELECT 2, 'D', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month;
/* company payroll */ SELECT 3, 'T', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month;
```

COUNT(*) counts joined payroll rows, not COUNT(DISTINCT employee_id). There is no employee-active or payment-status WHERE predicate. Multiple companies with the same company_name can be merged by GROUP BY; identity-dependent grouping/email rejects ambiguous company names through its separate lookup. [backend/app/payroll_source.py:44](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:44), [backend/app/payroll_source.py:213](/Users/apple/Desktop/ESC/backend/app/payroll_source.py:213).

## Tables and persistence map

| Tables | Read/write role |
|---|---|
| dbo.rjob | Parent configuration; insert/update; read/list/run |
| dbo.rjob_schedule_info | Schedule; delete/reinsert on edit; read/list/scheduler |
| dbo.rjob_file_detail | Mappings; delete/reinsert; read/render setup |
| dbo.rjob_client_detail | Recipient rows; delete/reinsert; read/mail |
| dbo.rjob_file_sorting_details | Sort-priority fallback; delete/reinsert/read |
| dbo.rjob_file_condition_details | Encoded thresholds; delete/reinsert/read |
| dbo.rjob_query | Saved approved templates and rule text; delete/reinsert/read; source inference |
| dbo.rjob_history | Run summary update/insert; dashboard read |
| dbo.rjob_history_details | Requested run-date inserts; dashboard reads globally latest detail row |
| dbo.rjob_result | Optional output JSON record inserts; no UI read endpoint in this flow |
| dbo.rjob_mapping_column | Mapping lookup read only in feature; populated/updated by migrations |
| dbo.rjob_file_typ | File-type/delimiter lookup read only in feature |
| dbo.rjobformat | Mapping format lookup read only in feature; output-name-like rows currently present but excluded |
| dbo.companies | Unique name/ID lookup, payroll Header input and joins; no feature writes |
| dbo.employees | Payroll join input; no feature writes |
| dbo.payroll | Source payroll_month/net_salary; no feature writes |
| prism.export.Client_Details | CSV client catalog; query verified in code; live availability/content NOT VERIFIED (endpoint 503) |

That is **17 referenced persistent data tables**, of which 16 dbo schemas were inspected through system metadata. This does not claim all referenced columns in the failed upstream client source were accessible. [DB evidence](evidence/read-only-database.json).

## Migrations versus runtime

Migrations 001–012 are scripts, not automatically applied by this app's startup. They define results storage, seed mapping/file catalogs/sample data, normalize output-name codes, and evolve payroll query logic. Do not execute them to perform this read-only analysis. `003` seeds net_salary as basic_salary+allowances-deductions and adds a computed gross_pay column; those are setup calculations, not per-run retirement formulas. The live schema confirms computed gross_pay; no assumption is made that all real payroll rows were created by this seed script. [backend/migrations/001_retirement_builder_results.sql:1](/Users/apple/Desktop/ESC/backend/migrations/001_retirement_builder_results.sql:1), [backend/migrations/003_sample_payroll_data.sql:90](/Users/apple/Desktop/ESC/backend/migrations/003_sample_payroll_data.sql:90).

Installed schema and procedure metadata were actually inspected without values. Full deployed scheduler executable behavior (`service/SchedulerAppBackend.exe`) is **NOT VERIFIED**; the traced browser API uses the Python code, and no binary was executed. Independent jobs/processes could exist outside this route's implementation.
