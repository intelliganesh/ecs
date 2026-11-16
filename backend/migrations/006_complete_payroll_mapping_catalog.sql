DECLARE @columns TABLE (
    table_name sysname NOT NULL,
    column_name varchar(255) PRIMARY KEY,
    display_name varchar(255) NOT NULL,
    field_type varchar(255) NOT NULL
);

INSERT INTO @columns VALUES
    ('dbo.companies', 'company_code', 'Company Code', 'text'),
    ('dbo.companies', 'city', 'Company City', 'text'),
    ('dbo.companies', 'company_email', 'Company Email', 'email'),
    ('dbo.companies', 'company_phone', 'Company Phone', 'phone'),
    ('dbo.employees', 'employee_code', 'Employee Code', 'text'),
    ('dbo.employees', 'department', 'Department', 'text'),
    ('dbo.employees', 'designation', 'Designation', 'text'),
    ('dbo.employees', 'is_active', 'Is Active', 'text'),
    ('dbo.employees', 'paydate', 'Employee Pay Date', 'date'),
    ('dbo.payroll', 'basic_salary', 'Basic Salary', 'number'),
    ('dbo.payroll', 'allowances', 'Allowances', 'number'),
    ('dbo.payroll', 'deductions', 'Deductions', 'number'),
    ('dbo.payroll', 'payment_status', 'Payment Status', 'text');

IF EXISTS (SELECT 1 FROM @columns WHERE COL_LENGTH(table_name, column_name) IS NULL)
    THROW 50004, 'A payroll mapping source column is missing. Apply the sample payroll migrations first.', 1;

INSERT INTO dbo.rjob_mapping_column (mapping_column, mapping_column_desc, mapping_column_dt)
SELECT column_name, display_name, field_type
FROM @columns AS source
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.rjob_mapping_column AS existing WITH (UPDLOCK, HOLDLOCK)
    WHERE existing.mapping_column = source.column_name
);
