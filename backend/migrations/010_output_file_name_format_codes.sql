SET XACT_ABORT ON;
BEGIN TRANSACTION;

BEGIN TRY
    DECLARE @whitespace nvarchar(4) = N' ' + NCHAR(9) + NCHAR(10) + NCHAR(13);
    DECLARE @formats TABLE (label varchar(50) PRIMARY KEY, code nvarchar(50) NOT NULL UNIQUE);
    INSERT INTO @formats (label, code) VALUES
        ('File Name', N'FILENAME'),
        ('Client ID', N'CLIENT'),
        ('Payday', N'PAYDAY'),
        ('File Name + Client ID', N'FILENAME_CLIENT'),
        ('File Name + Payday', N'FILENAME_PAYDAY'),
        ('Client ID + Payday', N'CLIENT_PAYDAY'),
        ('File Name + Client ID + Payday', N'FILENAME_CLIENT_PAYDAY');

    UPDATE lookup
    SET jobformattype = formats.code
    FROM dbo.rjobformat AS lookup
    JOIN @formats AS formats
        ON TRIM(@whitespace FROM lookup.jobformat) COLLATE Latin1_General_100_CI_AS = formats.label
    WHERE TRIM(@whitespace FROM lookup.jobformattype) COLLATE Latin1_General_100_CI_AS = N'output_file_name';

    IF EXISTS (
        SELECT 1 FROM @formats AS formats
        WHERE (SELECT COUNT(*) FROM dbo.rjobformat AS lookup WHERE lookup.jobformattype = formats.code) <> 1
    )
        THROW 50009, 'Each of the seven output filename codes needs one lookup row. Check migration 008 and the existing labels.', 1;

    UPDATE job
    SET FileNameFormat = formats.code
    FROM dbo.rjob AS job
    JOIN dbo.rjobformat AS lookup
        ON TRIM(@whitespace FROM job.FileNameFormat) COLLATE Latin1_General_100_CI_AS
         = TRIM(@whitespace FROM lookup.jobformat) COLLATE Latin1_General_100_CI_AS
    JOIN @formats AS formats ON lookup.jobformattype = formats.code
        AND TRIM(@whitespace FROM lookup.jobformat) COLLATE Latin1_General_100_CI_AS = formats.label
    WHERE NOT EXISTS (
        SELECT 1 FROM @formats AS existing
        WHERE job.FileNameFormat COLLATE Latin1_General_100_BIN2 = existing.code COLLATE Latin1_General_100_BIN2
          AND DATALENGTH(job.FileNameFormat) = LEN(existing.code)
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
