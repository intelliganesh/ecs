CREATE OR ALTER PROCEDURE dbo.usp_CompanyPayrollReport
    @jobid int = NULL,
    @templates_only bit = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @templates TABLE (recttype varchar(10), [Query] varchar(max));
    INSERT INTO @templates (recttype, [Query]) VALUES
        ('H', '/* company payroll */ SELECT 1, ''H'' AS RECTYPE, c.company_name, '''', 0, 0 FROM dbo.companies AS c'),
        ('D', '/* company payroll */ SELECT 2, ''D'', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month'),
        ('T', '/* company payroll */ SELECT 3, ''T'', c.company_name, p.payroll_month, COUNT(*) AS employee_count, SUM(p.net_salary) AS net_salary_total FROM dbo.companies AS c JOIN dbo.employees AS e ON e.company_id = c.id JOIN dbo.payroll AS p ON p.employee_id = e.id GROUP BY c.company_name, p.payroll_month');

    IF @templates_only = 1
    BEGIN
        SELECT recttype, [Query] FROM @templates;
        RETURN;
    END;

    DECLARE @records TABLE (recttype varchar(10), [Query] varchar(max));
    IF @jobid IS NULL
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

    DECLARE @sql nvarchar(max) =
        (SELECT [Query] FROM @records WHERE recttype = 'H') + N' UNION ALL '
        + (SELECT [Query] FROM @records WHERE recttype = 'D') + N' UNION ALL '
        + (SELECT [Query] FROM @records WHERE recttype = 'T') + N' ORDER BY 1, 3 DESC, 4;';
    EXEC sys.sp_executesql @sql;
END;
GO

DROP FUNCTION IF EXISTS dbo.ufn_CompanyPayrollRecordQueries;
