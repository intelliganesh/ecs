from datetime import date
from itertools import count
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field


router = APIRouter(prefix="/retirement-builder", tags=["retirement-builder"])


class GeneralForm(BaseModel):
    testfileName: str = ""
    fileName: str = ""
    fileFormat: str = ""
    description: str = ""
    outputFileNameFormat: str = ""
    enable: bool = True
    storeResultsToTable: bool = False
    selectedFile: str = ""


class ScheduleForm(BaseModel):
    startDate: date | None = None
    buildFrequency: Literal["Daily", "Weekly", "Bi-Weekly", "Monthly"] = "Weekly"
    hour: str = "4"
    minute: str = "00"
    meridiem: Literal["AM", "PM"] = "AM"
    week: Literal[
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ] = "Thursday"


class MappingRow(BaseModel):
    field: str = ""
    startPosition: str = ""
    length: str = ""
    recordType: str = ""
    defaultValue: str = ""
    mappingColumn: str = ""
    format: str = ""


class MappingForm(BaseModel):
    includeHeader: bool = True
    rows: list[MappingRow] = Field(default_factory=list)


class SubscriptionRow(BaseModel):
    client: str = ""
    email: str = ""


class SubscriptionsForm(BaseModel):
    mergeFiles: bool = False
    rows: list[SubscriptionRow] = Field(default_factory=list)


class SortingOrderRow(BaseModel):
    orderBy: str = ""
    mappingColumn: str = ""


class ConditionalStatementRow(BaseModel):
    mappingColumn: str = ""
    condition: str = ""
    value: str = ""


class FileSettingsForm(BaseModel):
    sortingOrder: list[SortingOrderRow] = Field(default_factory=list)
    conditionalStatements: list[ConditionalStatementRow] = Field(default_factory=list)


class RetirementBuilderJob(BaseModel):
    id: int
    general: GeneralForm = Field(default_factory=GeneralForm)
    schedule: ScheduleForm = Field(default_factory=ScheduleForm)
    mapping: MappingForm = Field(default_factory=MappingForm)
    subscriptions: SubscriptionsForm = Field(default_factory=SubscriptionsForm)
    fileSettings: FileSettingsForm = Field(default_factory=FileSettingsForm)


class RetirementBuilderJobInput(BaseModel):
    general: GeneralForm = Field(default_factory=GeneralForm)
    schedule: ScheduleForm = Field(default_factory=ScheduleForm)
    mapping: MappingForm = Field(default_factory=MappingForm)
    subscriptions: SubscriptionsForm = Field(default_factory=SubscriptionsForm)
    fileSettings: FileSettingsForm = Field(default_factory=FileSettingsForm)


class RetirementBuilderOptions(BaseModel):
    fileFormats: list[str]
    outputFileNameFormats: list[str]
    buildFrequencies: list[str]
    hours: list[str]
    minutes: list[str]
    meridiems: list[str]
    weekDays: list[str]
    recordTypes: list[str]
    mappingColumns: list[str]
    mappingFormats: list[str]


_jobs: dict[int, RetirementBuilderJob] = {}
_job_ids = count(1)


@router.get("/options", response_model=RetirementBuilderOptions)
def get_retirement_builder_options() -> RetirementBuilderOptions:
    return RetirementBuilderOptions(
        fileFormats=[
            "CSV (Comma Delimited)",
            "CSV (Pipe Delimited)",
            "CSV (Tab Delimited)",
            "CSV (Semicolon Delimited)",
        ],
        outputFileNameFormats=[
            "File Name",
            "Client ID",
            "Payday",
            "File Name + Client ID",
            "File Name + Payday",
            "Client ID + Payday",
            "File Name + Client ID + Payday",
        ],
        buildFrequencies=["Daily", "Weekly", "Bi-Weekly", "Monthly"],
        hours=[str(hour) for hour in range(1, 13)],
        minutes=[f"{minute:02d}" for minute in range(60)],
        meridiems=["AM", "PM"],
        weekDays=[
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ],
        recordTypes=["Header", "Detail", "Trailer"],
        mappingColumns=["Employee Work Email", "Pay Date"],
        mappingFormats=["LA - Left Justified", "MMDDYYYY - Date", "XXXXXXXXX - SSN"],
    )


@router.get("/jobs", response_model=list[RetirementBuilderJob])
def list_retirement_builder_jobs() -> list[RetirementBuilderJob]:
    return list(_jobs.values())


@router.post("/jobs", response_model=RetirementBuilderJob, status_code=status.HTTP_201_CREATED)
def create_retirement_builder_job(payload: RetirementBuilderJobInput) -> RetirementBuilderJob:
    job = RetirementBuilderJob(id=next(_job_ids), **payload.model_dump())
    _jobs[job.id] = job
    return job


@router.get("/jobs/{job_id}", response_model=RetirementBuilderJob)
def get_retirement_builder_job(job_id: int) -> RetirementBuilderJob:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
    return job


@router.put("/jobs/{job_id}", response_model=RetirementBuilderJob)
def update_retirement_builder_job(job_id: int, payload: RetirementBuilderJobInput) -> RetirementBuilderJob:
    if job_id not in _jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")
    job = RetirementBuilderJob(id=job_id, **payload.model_dump())
    _jobs[job_id] = job
    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_retirement_builder_job(job_id: int) -> None:
    if _jobs.pop(job_id, None) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retirement Builder job not found")


