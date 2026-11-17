CREATE OR ALTER FUNCTION dbo.ufn_CompanyPayrollRecordQueries()
RETURNS TABLE
AS
RETURN (
    SELECT recttype, CAST(query_text AS varchar(max)) AS [Query]
    FROM (VALUES
        ('H', '/* company payroll */ SELECT 1, ''H'' AS RECTYPE, c.company_name, '''', 0, 0 FROM dbo.companies AS c'),
        ('D', '/* company payroll */ SELECT 2, ''D'', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month'),
        ('T', '/* company payroll */ SELECT 3, ''T'', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month')
    ) AS templates(recttype, query_text)
);
GO

CREATE OR ALTER PROCEDURE dbo.usp_CompanyPayrollReport
    @jobid int = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @records TABLE (recttype varchar(10), [Query] varchar(max));
    IF @jobid IS NULL
        INSERT INTO @records SELECT recttype, [Query] FROM dbo.ufn_CompanyPayrollRecordQueries();
    ELSE
        INSERT INTO @records
        SELECT recttype, [Query] FROM dbo.rjob_query
        WHERE jobid = @jobid AND recttype IN ('H', 'D', 'T');

    -- Only execute SQL matching the server's approved SELECTs for each record type.
    IF (SELECT COUNT(*) FROM @records) <> 3 OR EXISTS (
        SELECT 1 FROM dbo.ufn_CompanyPayrollRecordQueries() AS expected
        WHERE NOT EXISTS (
            SELECT 1 FROM @records AS saved
            WHERE saved.recttype = expected.recttype
              AND HASHBYTES('SHA2_256', saved.[Query]) = HASHBYTES('SHA2_256', expected.[Query])
        )
    )
        THROW 50005, 'This payroll job needs one approved H, D, and T query.', 1;

    DECLARE @sql nvarchar(max) =
        (SELECT [Query] FROM @records WHERE recttype = 'H') + N' UNION ALL '
        + (SELECT [Query] FROM @records WHERE recttype = 'D') + N' UNION ALL '
        + (SELECT [Query] FROM @records WHERE recttype = 'T') + N' ORDER BY 1, 3 DESC, 4;';
    EXEC sys.sp_executesql @sql;
END;
GO

DECLARE @jobs TABLE (jobid int PRIMARY KEY);
INSERT INTO @jobs SELECT DISTINCT jobid FROM dbo.rjob_query WHERE recttype = 'PAYROLL' AND jobid IS NOT NULL;

IF EXISTS (
    SELECT 1 FROM dbo.rjob_query AS q JOIN @jobs AS j ON j.jobid = q.jobid
    WHERE q.recttype IN ('H', 'D', 'T')
)
    THROW 50006, 'A legacy payroll job already has H, D, or T rows.', 1;

INSERT INTO dbo.rjob_query (jobid, recttype, [Query], Conditions, Sort_Order)
SELECT jobs.jobid, template.recttype, template.[Query],
       CASE WHEN template.recttype = 'D' THEN COALESCE(conditions.clause, '') ELSE '' END,
       CASE WHEN template.recttype = 'D' AND sorting.clause IS NOT NULL THEN 'ORDER BY ' + sorting.clause ELSE '' END
FROM @jobs AS jobs
CROSS JOIN dbo.ufn_CompanyPayrollRecordQueries() AS template
OUTER APPLY (
    SELECT STRING_AGG(CAST(QUOTENAME(mapping_column) + ' '
        + CASE WHEN condition_symbol = '==' THEN '=' ELSE condition_symbol END + ' '
        + CONVERT(varchar(40), condition_value) AS varchar(max)), ' AND ')
        WITHIN GROUP (ORDER BY mapping_column) AS clause
    FROM dbo.rjob_file_condition_details WHERE job_id = jobs.jobid
) AS conditions
OUTER APPLY (
    SELECT STRING_AGG(CAST(QUOTENAME(mapping_column) + CASE WHEN sort_order < 0 THEN ' DESC' ELSE ' ASC' END AS varchar(max)), ', ')
        WITHIN GROUP (ORDER BY CASE WHEN sort_order < 0 THEN -CAST(sort_order AS bigint) - 1 ELSE sort_order END) AS clause
    FROM dbo.rjob_file_sorting_details WHERE job_id = jobs.jobid
) AS sorting;

DELETE q FROM dbo.rjob_query AS q JOIN @jobs AS j ON j.jobid = q.jobid WHERE q.recttype = 'PAYROLL';
