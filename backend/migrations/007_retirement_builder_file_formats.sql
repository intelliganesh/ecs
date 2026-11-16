INSERT INTO dbo.rjob_file_typ (filetyp, delimiter)
SELECT formats.filetyp, formats.delimiter
FROM (VALUES
    ('Comma', N','),
    ('Pipe', N'|'),
    ('Tab', NCHAR(9)),
    ('Semicolon', N';'),
    ('Space', NCHAR(32))
) AS formats(filetyp, delimiter)
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.rjob_file_typ AS existing WITH (UPDLOCK, HOLDLOCK)
    WHERE existing.filetyp = formats.filetyp
);
