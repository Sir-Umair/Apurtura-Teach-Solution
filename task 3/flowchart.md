# APTURA TECH SOLUTIONS - SYSTEM FLOWCHARTS
**1-Month Internship Program – Batch 02 | Week 03 Task**  
**Module:** System Architecture & Workflow Visualizations  

---

## 1. EMPLOYEE & ADMIN AUTHENTICATION FLOW

```mermaid
flowchart TD
    Start([User Launch Application]) --> InputCredentials[Input Username/EmpID & Password]
    InputCredentials --> HashCheck[Hash Password using SHA-256 + Salt]
    HashCheck --> FetchUser{User Exists in Database?}
    FetchUser -- No --> AuthFail[Display 'Invalid Credentials' & Log Failure]
    AuthFail --> InputCredentials
    FetchUser -- Yes --> MatchHash{Hash Matches Database Hash?}
    MatchHash -- No --> AuthFail
    MatchHash -- Yes --> CheckRole{Check User Role}
    CheckRole -- Admin --> AdminMenu[Display Admin Master Menu]
    CheckRole -- Employee --> EmpMenu[Display Employee Standard Menu]
```

---

## 2. ATTENDANCE MANAGEMENT (CLOCK IN / CLOCK OUT) FLOW

```mermaid
flowchart TD
    StartAttendance([Select Clock In/Out]) --> GetToday[Get Current Date & Time]
    GetToday --> QueryRecord{Record Exists for Today?}
    
    QueryRecord -- No --> ConfirmClockIn[Prompt: 'Clock In Now?']
    ConfirmClockIn -- Yes --> CreateRecord[Create Attendance Record: status='In Progress']
    CreateRecord --> AtomicSave[Atomic Database Save JSON/WAL]
    AtomicSave --> SuccessMsg[Display 'Clocked IN Successfully']

    QueryRecord -- Yes --> CheckClockOut{Already Clocked Out?}
    CheckClockOut -- Yes --> AlreadyDone[Display 'Shift Already Completed Today']
    CheckClockOut -- No --> ConfirmClockOut[Prompt: 'Clock Out Now?']
    ConfirmClockOut -- Yes --> CalcHours[Calculate worked_hours = ClockOut - ClockIn]
    CalcHours --> UpdateRecord[Update Record: status='Present', hours_worked]
    UpdateRecord --> AtomicSave
    AtomicSave --> SuccessMsgOut[Display 'Clocked OUT Successfully']
```

---

## 3. SALARY & OVERTIME CALCULATION ENGINE FLOW

```mermaid
flowchart TD
    StartCalc([Initiate Payroll Calculation]) --> FetchAttendance[Fetch Attendance Records for Employee]
    FetchAttendance --> LoopRecords[Iterate through Daily Attendance Records]
    LoopRecords --> CheckDailyHours{Hours Worked > 8.0?}
    
    CheckDailyHours -- Yes --> AddRegular[Regular Hours += 8.0]
    AddRegular --> AddOvertime[Overtime Hours += Worked - 8.0]
    
    CheckDailyHours -- No --> AddNormal[Regular Hours += Worked]
    
    AddOvertime --> CheckNext{More Records?}
    AddNormal --> CheckNext
    
    CheckNext -- Yes --> LoopRecords
    CheckNext -- No --> CalcBasePay[Regular Pay = Regular Hours * Hourly Rate]
    CalcBasePay --> CalcOTPay[Overtime Pay = Overtime Hours * Hourly Rate * 1.5]
    CalcOTPay --> CalcGross[Gross Pay = Regular Pay + Overtime Pay]
    CalcGross --> CalcTax[Tax Deduction = Gross Pay * Tax Rate]
    CalcTax --> CalcNet[Net Pay = Gross Pay - Tax Deduction]
    CalcNet --> ReturnStatement([Return Detailed Payroll Statement])
```

---

## 4. REPORT GENERATION & EXPORT FLOW (CSV / PDF)

```mermaid
flowchart TD
    StartExport([Admin Selects Generate Monthly Report]) --> PromptMonth[Enter Target Month YYYY-MM / All]
    PromptMonth --> BatchCalc[Run Payroll Engine for All Active Employees]
    BatchCalc --> DisplayTable[Render Summary Table on Terminal CLI]
    DisplayTable --> SelectFormat{Select Export Format}
    
    SelectFormat -- CSV --> ExportCSV[Write Data via csv.DictWriter]
    ExportCSV --> ConfirmCSV[CSV File Generated Successfully]
    
    SelectFormat -- PDF --> CheckReportLab{ReportLab Installed?}
    CheckReportLab -- Yes --> BuildPDFDoc[Build Styled PDF Doc with Tables & Header]
    BuildPDFDoc --> ConfirmPDF[PDF File Generated Successfully]
    CheckReportLab -- No --> PDFError[Display Install Requirement Error]
    
    SelectFormat -- Both --> ExportCSV
    ExportCSV --> CheckReportLab
```

---

## 5. ATOMIC DATA WRITE & CORRUPTION RECOVERY FLOW

```mermaid
flowchart TD
    StartSave([Save Database Request]) --> CopyBackup[Create Backup Copy: payroll_database.json.bak]
    CopyBackup --> WriteTemp[Write JSON Data to Temporary File: payroll_database.json.tmp]
    WriteTemp --> VerifyWrite{Write Successful & Valid?}
    
    VerifyWrite -- Yes --> ReplaceFile[Atomic File Replace: tmp -> primary json]
    ReplaceFile --> SaveSuccess([Save Complete])
    
    VerifyWrite -- No --> RemoveTemp[Delete Temporary File]
    RemoveTemp --> SaveError([Return Save Error])
    
    %% Recovery Loop
    StartLoad([App Startup Load Data]) --> ReadPrimary{Primary File Valid JSON?}
    ReadPrimary -- Yes --> ReturnData([Data Loaded Successfully])
    ReadPrimary -- No --> DetectCorruption[Intercept Corruption Error]
    DetectCorruption --> CheckBackup{Backup File Exists?}
    CheckBackup -- Yes --> RestoreBackup[Copy Backup -> Primary File]
    RestoreBackup --> ReturnData
    CheckBackup -- No --> ReinitDefaults[Initialize Default Admin & Database]
    ReinitDefaults --> ReturnData
```
