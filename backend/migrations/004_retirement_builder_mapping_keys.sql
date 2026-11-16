-- Keep the source identifiers and display labels separate.
DECLARE @mapping_keys TABLE (
    label varchar(255) PRIMARY KEY,
    source_name varchar(255) NOT NULL UNIQUE
);

INSERT INTO @mapping_keys VALUES
    ('Client ID', 'company_id'),
    ('Company Name', 'company_name'),
    ('Date', 'pay_date'),
    ('Date of Birth', 'date_of_birth'),
    ('Employee Count', 'employee_count'),
    ('Employee ID', 'employee_id'),
    ('Employee Name', 'employee_name'),
    ('Employee Work Email', 'work_email'),
    ('First Name', 'first_name'),
    ('Gross Pay', 'gross_pay'),
    ('Hire Date', 'hire_date'),
    ('Hours Worked', 'hours_worked'),
    ('Last Name', 'last_name'),
    ('Net Salary', 'net_salary'),
    ('Net Salary Total', 'net_salary_total'),
    ('Pay Date', 'payroll_month'),
    ('Pay End Date', 'pay_end_date'),
    ('Pay Start Date', 'pay_start_date'),
    ('Phone', 'phone'),
    ('Record Type', 'rectype'),
    ('SSN', 'ssn'),
    ('Termination Date', 'termination_date');

IF EXISTS (
    SELECT keys.source_name
    FROM dbo.rjob_mapping_column AS mapping WITH (UPDLOCK, HOLDLOCK)
    JOIN @mapping_keys AS keys
        ON LTRIM(RTRIM(mapping.mapping_column)) IN (keys.label, keys.source_name)
    GROUP BY keys.source_name
    HAVING COUNT(*) > 1
)
    THROW 50003, 'Multiple mapping rows resolve to the same source name.', 1;

UPDATE mapping
SET mapping_column = keys.source_name,
    mapping_column_desc = COALESCE(NULLIF(LTRIM(RTRIM(mapping.mapping_column_desc)), ''), keys.label)
FROM dbo.rjob_mapping_column AS mapping
JOIN @mapping_keys AS keys ON LTRIM(RTRIM(mapping.mapping_column)) = keys.label
WHERE mapping.mapping_column COLLATE Latin1_General_100_BIN2 <> keys.source_name COLLATE Latin1_General_100_BIN2
   OR mapping.mapping_column_desc IS NULL OR LTRIM(RTRIM(mapping.mapping_column_desc)) = '';
