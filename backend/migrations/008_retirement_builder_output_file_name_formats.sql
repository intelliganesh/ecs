INSERT INTO dbo.rjobformat (jobformat, jobformat_desc, jobformattype)
SELECT formats.jobformat, formats.jobformat_desc, N'output_file_name'
FROM (VALUES
    ('File Name', 'One file with the job name'),
    ('Client ID', 'One file per client'),
    ('Payday', 'One file per pay date'),
    ('File Name + Client ID', 'Job name and client'),
    ('File Name + Payday', 'Job name and pay date'),
    ('Client ID + Payday', 'One file per client and pay date'),
    ('File Name + Client ID + Payday', 'Job name, client, and pay date')
) AS formats(jobformat, jobformat_desc)
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.rjobformat AS existing WITH (UPDLOCK, HOLDLOCK)
    WHERE existing.jobformat = formats.jobformat AND existing.jobformattype = N'output_file_name'
);
