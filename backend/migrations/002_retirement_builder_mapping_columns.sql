INSERT INTO dbo.rjob_mapping_column (mapping_column, mapping_column_desc, mapping_column_dt)
SELECT defaults.column_name, defaults.column_name, defaults.column_type
FROM (VALUES
    ('Client ID', 'text'),
    ('Company Name', 'text'),
    ('Date', 'date'),
    ('Date of Birth', 'date'),
    ('Employee Count', 'number'),
    ('Employee ID', 'text'),
    ('Employee Name', 'text'),
    ('Employee Work Email', 'email'),
    ('First Name', 'text'),
    ('Gross Pay', 'number'),
    ('Hire Date', 'date'),
    ('Hours Worked', 'number'),
    ('Last Name', 'text'),
    ('Net Salary', 'number'),
    ('Net Salary Total', 'number'),
    ('Pay Date', 'date'),
    ('Pay End Date', 'date'),
    ('Pay Start Date', 'date'),
    ('Phone', 'phone'),
    ('Record Type', 'text'),
    ('SSN', 'ssn'),
    ('Termination Date', 'date')
) AS defaults(column_name, column_type)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.rjob_mapping_column AS existing WITH (UPDLOCK, HOLDLOCK)
    WHERE LOWER(LTRIM(RTRIM(existing.mapping_column))) = LOWER(defaults.column_name)
);
