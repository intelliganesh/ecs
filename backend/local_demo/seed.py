"""Insert synthetic Prism fixtures only; preserve all existing records and jobs."""
import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path

import pyodbc
from dotenv import dotenv_values

from bootstrap import ROOT, quote


def fixtures():
    rows = defaultdict(list)
    for code, description, bill in [('REG', 'Demo regular pay', 'REG'), ('O/T', 'Demo overtime', 'REG'),
                                    ('TIPS', 'Demo reported tips', 'REG'), ('REIMB', 'Demo reimbursement', 'EXPS')]:
        rows['EARNING_CODES'].append(dict(u2_id=code, Pay_Code=code, Pay_Code_Desc=description, Bill_Code=bill, Pay_Reason_Code='R'))
    rows['JOB_CODE_MASTER'].append(dict(u2_id='DEMOCLASS', Job_Class_Code='DEMOCLASS', Job_Class_Desc='Demo office role'))
    rows['JOB_CODE_MASTER_WC'].append(dict(JOB_CODE_MASTER_WC_ID=990001, u2_id='DEMOCLASS', JOB_CLASS_CODE1='DEMOCLASS', WC_Class_Code='8810', WC_State='NY'))
    for number, label in [(901, 'Demo Harbor Services'), (902, 'Demo Maple Works')]:
        client = f'{number:06d}'
        rows['CLIENT_DETAILS'].append(dict(u2_id=client, Client_ID=client, Client_DBA_Name=label,
            Client_Legal_Name=label, Client_Status_Code='A', Federal_ID=f'00-0000{number}',
            Client_Email=f'client{number}@example.invalid', Client_Phone_No='2125550100'))
        rows['LOCATION_CODESS'].append(dict(u2_id=client+'*DEMO', Client_ID=client, Loc_Code='DEMO', Loc_Name='Demo office', Loc_ADDR_State='NY'))
        rows['JOB_CODES'].append(dict(u2_id=client+'*DEMO', Client_ID=client, Job_Code='DEMO', Job_Class_Code='DEMOCLASS', Job_Title='Demo analyst'))
        for index, code in enumerate(('REG', 'O/T', 'TIPS', 'REIMB')):
            rows['CLIENT_DETAILS_PAY_CODES'].append(dict(CLIENT_DETAILS_PAY_CODES_ID=990000+number*10+index, u2_id=client, Pay_Code=code))
    employees = [('000901', 'D00901', 'Avery', 'Demo', 25), ('000901', 'D00902', 'Jordan', 'Sample', 30),
                 ('000902', 'D00903', 'Casey', 'Example', 28)]
    dates = [date(2026, 10, 15), date(2026, 11, 13), date(2026, 11, 20), date(2026, 11, 24)]
    for employee_no, (client, employee, first, last, rate) in enumerate(employees, 1):
        rows['EMPLOYEE_PER'].append(dict(u2_id=employee, EE_ID=employee, EE_First_Name=first, EE_Last_Name=last,
            EE_Middle_Initial='D', EE_Birth_Date=date(1990, 1, employee_no), Gender_Code='X', Marital_Status_Code='S',
            EE_ADDR_Home_Line_1=f'{employee_no} Demo Lane', EE_ADDR_Home_City='Demo City', EE_ADDR_Home_State='NY',
            EE_ADDR_Home_Zip_Code='00000', EE_Email=f'employee{employee_no}@example.invalid', EE_Phone_1_No=f'212555010{employee_no}'))
        rows['EMPLOYEE_COM'].append(dict(u2_id=client+'*'+employee, Client_ID=client, EE_ID=employee, EE_No=str(employee_no),
            EE_Status_Code='A', EE_Status_Date=date(2025, 1, 1), EE_Last_Hire_Date=date(2025, 1, 1),
            EE_Seniority_Date=date(2025, 1, 1), Home_Loc_Code='DEMO', EE_Job_Code='DEMO', Home_Dept_Code='OFFICE',
            EE_Type_Code='F', RETIREMENT_BEN_GROUP='5', Officer_YN='N', WORK_EMAIL_ADDRESS=f'employee{employee_no}@example.invalid'))
        rows['EMPLOYEE_PAY'].append(dict(u2_id=client+'*'+employee, Client_ID=client, EE_ID=employee,
            EE_SSN=f'00000{employee_no:04d}', Pay_Annual_Rate=rate*2080))
        rows['EMPLOYEE_401K_DETAIL'].append(dict(u2_id=client+'*'+employee, Client_ID=client, EE_ID=employee,
            Retire_Eff_Date=date(2025, 1, 1), Highly_Comp_YN='N', Key_EE_YN='N', Elec_Pct=5, Roth_Pct=2))
        rows['EMPLOYEE_PAYROLL_REGISTER'].append(dict(u2_id=client+'*'+employee+'*2026', Client_ID=client,
            EE_ID=employee, GROSS_EARN=rate*160+400, HOURS_WORKED=168))
        rows['EMPLOYEE_401K_LOANS'].append(dict(u2_id=client+'*'+employee+'*1', Client_ID=client, EE_ID=employee,
            Loan_ID='1', TPA_Loan_No='DEMO1', Loan_Date=date(2026, 1, 1), Dedn_Start_Date=date(2026, 2, 1),
            Loan_Amt=1000, Pay_Back_Amt=1000, Paid_Amt=200, Payment_Amt=25))
        for date_no, payday in enumerate(dates, 1):
            voucher = client+'*'+employee+'*'+payday.strftime('%Y%m%d')
            gross = rate*40 + rate*1.5*4 + 50
            rows['EPV'].append(dict(u2_id=voucher, Client_ID=client, EE_ID=employee, Pay_Date=payday,
                Pay_Period_Start_Date=payday-timedelta(days=13), Pay_Period_End_Date=payday-timedelta(days=1),
                R_VOID_DATE=date(1900, 1, 1), VCHR_NO=str(employee_no*100+date_no), HOME_DEPARTMENT='OFFICE',
                HOME_DIVISION='DEMO', Pay_Group_Code='DEMO', Tot_Earn_Cash_Amt=gross+20, EXPENSE_REIMB=20,
                Retirement_Base_Earn_Amt=gross, Retirement_Pre_Tax_Amt=50, Retirement_Roth_Amt=20,
                Retirement_Loan_Pay_Amt=25, Retirement_Match_Amt=30, Retirement_Safe_1=10,
                Retirement_Safe_2=5, Retirement_Non_Elec_Match_Amt=8))
            for index, (code, hours, amount) in enumerate((('REG', 40, rate*40), ('O/T', 4, rate*1.5*4), ('TIPS', 0, 50), ('REIMB', 0, 20)), 1):
                rows['EPV_EARNINGS'].append(dict(EPV_EARNINGS_ID=9900000+employee_no*1000+date_no*10+index,
                    u2_id=voucher, TS_Pay_Code=code, TS_Hours_Units=hours, TS_Hours_Worked_Amt=hours,
                    TS_Earn_Amt=amount, TS_Rate=rate, TS_WC_Class_Code='8810'))
            for index, (code, description, amount) in enumerate((('K', 'Demo 401k pretax', 50), ('KR', 'Demo Roth', 20), ('KL', 'Demo 401k loan', 25)), 1):
                rows['EPV_DEDUCTIONS'].append(dict(EPV_DEDUCTIONS_ID=9900000+employee_no*1000+date_no*10+index,
                    u2_id=voucher, Dedn_Code=code, Dedn_Type_Code=code, Dedn_Desc=description, Dedn_Amt=amount))
            rows['EPV_OTHER_EARNINGS'].append(dict(EPV_OTHER_EARNINGS_ID=9900000+employee_no*1000+date_no,
                u2_id=voucher, Pay_Other_Code='REIMB', Pay_Other_Desc='Demo reimbursement', Pay_Other_Amt=20))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--expected-server', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    config = dotenv_values(ROOT / '.env')
    if config['DB_HOST'] != '127.0.0.1' or config['DB_NAME'] != 'ecs':
        raise SystemExit('Only the local ecs/Prism sandbox is allowed.')
    password = config['DB_PASSWORD'].replace('}', '}}')
    connection = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;DATABASE=prism;UID=sa;'
        f'PWD={{{password}}};TrustServerCertificate=yes', timeout=10)
    cursor = connection.cursor()
    if cursor.execute("SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(128))").fetchval() != args.expected_server:
        raise SystemExit('Local server identity mismatch; nothing inserted.')
    metadata = json.loads((args.snapshot / 'prism-columns.json').read_text())
    keys = json.loads((args.snapshot / 'prism-keys.json').read_text())
    report = {}
    for table, records in fixtures().items():
        columns = {row['column_name'].lower(): row for row in metadata if row['table_name'] == table}
        primary = [row['column_name'] for row in keys if row['table_name'] == table]
        inserted, skipped = 0, 0
        for record in records:
            unknown = set(k.lower() for k in record) - columns.keys()
            if unknown:
                raise ValueError(f'{table}: unknown fixture columns {unknown}')
            values = {columns[k.lower()]['column_name']: v for k, v in record.items()}
            for column in columns.values():
                name = column['column_name']
                if name not in values and column['type_name'] == 'numeric':
                    values[name] = 0
            where = ' AND '.join(quote(key) + '=?' for key in primary)
            if cursor.execute(f'SELECT 1 FROM export.{quote(table)} WHERE ' + where, tuple(values[key] for key in primary)).fetchone():
                skipped += 1
                continue
            sql = f'INSERT INTO export.{quote(table)} (' + ','.join(quote(k) for k in values) + ') VALUES (' + ','.join('?' for _ in values) + ')'
            if args.apply:
                cursor.execute(sql, tuple(values.values()))
            inserted += 1
        report[table] = {'inserted' if args.apply else 'planned': inserted, 'existing_keys_preserved': skipped}
    if args.apply:
        connection.commit()
    else:
        connection.rollback()
    connection.close()
    (args.snapshot / 'demo-data-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
