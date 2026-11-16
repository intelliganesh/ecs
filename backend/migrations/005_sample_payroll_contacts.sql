IF COL_LENGTH('dbo.companies', 'company_email') IS NULL
    ALTER TABLE dbo.companies ADD company_email varchar(254) NULL;
IF COL_LENGTH('dbo.companies', 'company_phone') IS NULL
    ALTER TABLE dbo.companies ADD company_phone varchar(32) NULL;
GO

-- Complete the original QA fixture and keep any contact details already set.
UPDATE dbo.companies
SET company_email = COALESCE(NULLIF(TRIM(company_email), ''), 'payroll@qa-company.example.invalid'),
    company_phone = COALESCE(NULLIF(TRIM(company_phone), ''), '202-555-0110')
WHERE company_name = 'QA Payroll Sample Company'
  AND (NULLIF(TRIM(company_email), '') IS NULL OR NULLIF(TRIM(company_phone), '') IS NULL);

UPDATE employee
SET first_name = COALESCE(NULLIF(TRIM(employee.first_name), N''), N'Sample'),
    last_name = COALESCE(NULLIF(TRIM(employee.last_name), N''), N'Payroll Employee'),
    work_email = COALESCE(NULLIF(TRIM(employee.work_email), ''), 'sample.payroll.employee@example.invalid'),
    phone = COALESCE(NULLIF(TRIM(employee.phone), ''), '202-555-0100'),
    date_of_birth = COALESCE(employee.date_of_birth, CONVERT(date, '19900215', 112)),
    hire_date = COALESCE(employee.hire_date, CONVERT(date, '20210104', 112))
FROM dbo.employees AS employee
JOIN dbo.companies AS company ON company.id = employee.company_id
WHERE company.company_name = 'QA Payroll Sample Company'
  AND employee.employee_code = 'QA-PAYROLL-001'
  AND (NULLIF(TRIM(employee.first_name), N'') IS NULL OR NULLIF(TRIM(employee.last_name), N'') IS NULL
       OR NULLIF(TRIM(employee.work_email), '') IS NULL OR NULLIF(TRIM(employee.phone), '') IS NULL
       OR employee.date_of_birth IS NULL OR employee.hire_date IS NULL);

UPDATE payroll
SET pay_start_date = COALESCE(payroll.pay_start_date, CONVERT(date, '20261101', 112)),
    pay_end_date = COALESCE(payroll.pay_end_date, CONVERT(date, '20261111', 112)),
    pay_date = COALESCE(payroll.pay_date, CONVERT(date, '20261111', 112)),
    hours_worked = COALESCE(payroll.hours_worked, 64.00)
FROM dbo.payroll AS payroll
JOIN dbo.employees AS employee ON employee.id = payroll.employee_id
JOIN dbo.companies AS company ON company.id = employee.company_id
WHERE company.company_name = 'QA Payroll Sample Company'
  AND employee.employee_code = 'QA-PAYROLL-001'
  AND payroll.payroll_month = CONVERT(date, '20261101', 112)
  AND (payroll.pay_start_date IS NULL OR payroll.pay_end_date IS NULL
       OR payroll.pay_date IS NULL OR payroll.hours_worked IS NULL);
