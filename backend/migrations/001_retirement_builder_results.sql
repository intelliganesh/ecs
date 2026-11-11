IF OBJECT_ID(N'dbo.rjob_result', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rjob_result (
        run_id uniqueidentifier NOT NULL,
        job_id int NOT NULL,
        row_number int NOT NULL,
        record_type char(1) NOT NULL,
        row_values nvarchar(max) NOT NULL,
        created_at datetime2(3) NOT NULL CONSTRAINT DF_rjob_result_created_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_rjob_result PRIMARY KEY (run_id, row_number),
        CONSTRAINT CK_rjob_result_row_number CHECK (row_number > 0),
        CONSTRAINT CK_rjob_result_record_type CHECK (record_type IN ('H', 'D', 'T')),
        CONSTRAINT CK_rjob_result_row_values CHECK (ISJSON(row_values) = 1)
    );

    CREATE INDEX IX_rjob_result_job_id ON dbo.rjob_result (job_id, created_at);
END;
