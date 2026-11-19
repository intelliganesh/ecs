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
