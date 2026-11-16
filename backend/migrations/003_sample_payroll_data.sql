-- Add sample attributes without changing the existing payroll procedure or report queries.
IF COL_LENGTH('dbo.companies', 'company_code') IS NULL
    ALTER TABLE dbo.companies ADD company_code varchar(40) NULL;
IF COL_LENGTH('dbo.companies', 'city') IS NULL
    ALTER TABLE dbo.companies ADD city nvarchar(100) NULL;

IF COL_LENGTH('dbo.employees', 'first_name') IS NULL
    ALTER TABLE dbo.employees ADD first_name nvarchar(80) NULL;
IF COL_LENGTH('dbo.employees', 'last_name') IS NULL
    ALTER TABLE dbo.employees ADD last_name nvarchar(80) NULL;
IF COL_LENGTH('dbo.employees', 'work_email') IS NULL
    ALTER TABLE dbo.employees ADD work_email varchar(254) NULL;
IF COL_LENGTH('dbo.employees', 'phone') IS NULL
    ALTER TABLE dbo.employees ADD phone varchar(32) NULL;
IF COL_LENGTH('dbo.employees', 'ssn') IS NULL
    ALTER TABLE dbo.employees ADD ssn varchar(9) NULL;
IF COL_LENGTH('dbo.employees', 'date_of_birth') IS NULL
    ALTER TABLE dbo.employees ADD date_of_birth date NULL;
IF COL_LENGTH('dbo.employees', 'hire_date') IS NULL
    ALTER TABLE dbo.employees ADD hire_date date NULL;
IF COL_LENGTH('dbo.employees', 'termination_date') IS NULL
    ALTER TABLE dbo.employees ADD termination_date date NULL;

IF COL_LENGTH('dbo.payroll', 'pay_start_date') IS NULL
    ALTER TABLE dbo.payroll ADD pay_start_date date NULL;
IF COL_LENGTH('dbo.payroll', 'pay_end_date') IS NULL
    ALTER TABLE dbo.payroll ADD pay_end_date date NULL;
IF COL_LENGTH('dbo.payroll', 'pay_date') IS NULL
    ALTER TABLE dbo.payroll ADD pay_date date NULL;
IF COL_LENGTH('dbo.payroll', 'hours_worked') IS NULL
    ALTER TABLE dbo.payroll ADD hours_worked decimal(6, 2) NULL;
IF COL_LENGTH('dbo.payroll', 'gross_pay') IS NULL
    ALTER TABLE dbo.payroll ADD gross_pay AS CONVERT(decimal(13, 2), basic_salary + allowances);
GO

-- Populate the known local sample company. Keeping one company preserves single-company
-- report output for existing jobs and subscriptions.
DECLARE @company_id int;
SELECT @company_id = id FROM dbo.companies WITH (UPDLOCK, HOLDLOCK)
WHERE company_name = 'QA Payroll Sample Company';

IF @company_id IS NULL
    THROW 50001, 'The local QA Payroll Sample Company is required to seed sample payroll data.', 1;

UPDATE dbo.companies
SET company_code = COALESCE(company_code, 'QA-PAYROLL'),
    city = COALESCE(city, N'Buffalo')
WHERE id = @company_id AND (company_code IS NULL OR city IS NULL);

DECLARE @employees TABLE (
    employee_code varchar(40) PRIMARY KEY,
    first_name nvarchar(80) NOT NULL,
    last_name nvarchar(80) NOT NULL,
    department nvarchar(100) NOT NULL,
    designation nvarchar(120) NOT NULL,
    work_email varchar(254) NOT NULL,
    phone varchar(32) NOT NULL,
    date_of_birth date NOT NULL,
    hire_date date NOT NULL,
    basic_salary decimal(12, 2) NOT NULL,
    allowances decimal(12, 2) NOT NULL,
    deductions decimal(12, 2) NOT NULL
);

INSERT INTO @employees VALUES
    ('RB-QA-101', N'Maya', N'Reed', N'Finance', N'Payroll Analyst', 'maya.reed@example.invalid', '202-555-0101', '19910514', '20220307', 4200.00, 180.00, 330.00),
    ('RB-QA-102', N'Theo', N'Morgan', N'Operations', N'Operations Coordinator', 'theo.morgan@example.invalid', '202-555-0102', '19890922', '20230109', 3650.00, 125.00, 275.00),
    ('RB-QA-103', N'Nina', N'Park', N'Support', N'Support Specialist', 'nina.park@example.invalid', '202-555-0103', '19970518', '20240603', 3150.00, 90.00, 220.00);

IF EXISTS (
    SELECT 1 FROM @employees AS sample
    JOIN dbo.employees AS employee ON employee.employee_code = sample.employee_code
    WHERE employee.company_id <> @company_id OR employee.work_email IS NULL OR employee.work_email <> sample.work_email
)
    THROW 50002, 'A sample employee code is already used by a different employee.', 1;

INSERT INTO dbo.employees (
    employee_code, employee_name, company_id, department, designation, is_active, paydate,
    first_name, last_name, work_email, phone, date_of_birth, hire_date
)
SELECT sample.employee_code, CONCAT(sample.first_name, N' ', sample.last_name), @company_id,
       sample.department, sample.designation, 1, '20261113',
       sample.first_name, sample.last_name, sample.work_email, sample.phone, sample.date_of_birth, sample.hire_date
FROM @employees AS sample
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.employees AS employee WITH (UPDLOCK, HOLDLOCK)
    WHERE employee.employee_code = sample.employee_code
);

INSERT INTO dbo.payroll (
    employee_id, payroll_month, basic_salary, allowances, deductions, net_salary,
    payment_status, pay_start_date, pay_end_date, pay_date, hours_worked
)
SELECT employee.id, period.payroll_month, sample.basic_salary, sample.allowances, sample.deductions,
       sample.basic_salary + sample.allowances - sample.deductions, 'Paid',
       period.payroll_month, period.pay_end_date, period.pay_date, period.hours_worked
FROM @employees AS sample
JOIN dbo.employees AS employee ON employee.employee_code = sample.employee_code AND employee.company_id = @company_id
CROSS JOIN (VALUES
    (CONVERT(date, '20260901'), CONVERT(date, '20260930'), CONVERT(date, '20261002'), 160.00),
    (CONVERT(date, '20261001'), CONVERT(date, '20261031'), CONVERT(date, '20261102'), 168.00),
    (CONVERT(date, '20261101'), CONVERT(date, '20261113'), CONVERT(date, '20261113'), 80.00)
) AS period(payroll_month, pay_end_date, pay_date, hours_worked)
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.payroll AS payroll WITH (UPDLOCK, HOLDLOCK)
    WHERE payroll.employee_id = employee.id AND payroll.payroll_month = period.payroll_month
);
