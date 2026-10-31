# OEE Data Dictionary

This document defines the core schema used by the synthetic manufacturing OEE workflow.

## Plant

- plant_id: string, required, unique, format PLT-0001
- plant_name: string, required, free text
- country: string, required, ISO country code
- timezone: string, required, UTC±HH:MM
- status: enum, required, active|inactive|maintenance

## Line

- line_id: string, required, unique, format LIN-0001
- plant_id: string, required, FK to Plant.plant_id
- line_name: string, required, free text
- line_type: enum, required, packaging|assembly|forming|machining|finishing
- status: enum, required, active|paused|maintenance

## Machine

- machine_id: string, required, unique, format MCH-0001
- line_id: string, required, FK to Line.line_id
- machine_name: string, required, free text
- machine_class: enum, required, press|mixer|labeler|injector|packer|tester
- ideal_cycle_seconds: integer, required, > 0, seconds
- status: enum, required, available|down|maintenance|offline

## Shift

- shift_id: string, required, unique, format SHIFT-YYYY-MM-DD-A
- shift_date: date, required, YYYY-MM-DD
- shift_code: enum, required, A|B|C
- start_ts: datetime, required, ISO timestamp, before end_ts
- end_ts: datetime, required, ISO timestamp, after start_ts
- planned_break_minutes: integer, required, 0-120

## Product

- product_id: string, required, unique, format PRD-0001
- product_name: string, required, free text
- family: string, required, free text
- ideal_cycle_seconds: integer, required, > 0, seconds/unit
- uom: enum, required, pcs|kg|box

## ProductionOrder

- production_order_id: string, required, unique, format PO-2026-000001
- machine_id: string, required, FK to Machine.machine_id
- product_id: string, required, FK to Product.product_id
- shift_id: string, required, FK to Shift.shift_id
- planned_qty: integer, required, > 0
- actual_qty: integer, optional, derived from counts
- status: enum, required, planned|running|complete|held|cancelled
- start_ts: datetime, required, before end_ts
- end_ts: datetime, required, after start_ts

## StateEvent

- state_event_id: string, required, unique, format EVT-MCH-0001-000001
- machine_id: string, required, FK to Machine.machine_id
- shift_id: string, required, FK to Shift.shift_id
- production_order_id: string, optional, FK to ProductionOrder.production_order_id
- state_from: enum, optional, IDLE|RUN|DOWN|SETUP|BREAK|OFFLINE|MAINTENANCE
- state_to: enum, required, IDLE|RUN|DOWN|SETUP|BREAK|OFFLINE|MAINTENANCE
- event_ts: datetime, required, inside shift window
- duration_seconds: integer, required, >=0
- reason_code: string, optional, FK to DowntimeReason.reason_code
- is_planned: boolean, optional, planned downtime flag
- anomaly_flag: string, optional, none|overlap|downtime_overlap|count_decrease|scrap_excess|wrong_cycle_time

## ProductionCount

- count_id: string, required, unique, format CNT-PO-2026-000001
- production_order_id: string, required, FK to ProductionOrder.production_order_id
- machine_id: string, required, FK to Machine.machine_id
- product_id: string, required, FK to Product.product_id
- shift_id: string, required, FK to Shift.shift_id
- count_ts: datetime, required, within shift
- count_type: enum, required, good|scrap|rework|correction
- quantity: integer, required, >=0
- correction_flag: boolean, required
- source_state_event_id: string, optional, FK to StateEvent.state_event_id

## QualityInspection

- inspection_id: string, required, unique, format QC-2026-000001
- production_order_id: string, required, FK to ProductionOrder.production_order_id
- machine_id: string, required, FK to Machine.machine_id
- product_id: string, required, FK to Product.product_id
- shift_id: string, required, FK to Shift.shift_id
- inspection_ts: datetime, required
- sample_qty: integer, required, >=0
- good_qty: integer, required, >=0, good_qty <= sample_qty
- scrap_qty: integer, required, >=0, scrap_qty <= sample_qty
- rework_qty: integer, required, >=0, rework_qty <= sample_qty
- pass_flag: boolean, required, true when good_qty >= 0.95 \* sample_qty
- defect_code: string, optional, D001|D015|D033|D041|D099|NONE
- anomaly_flag: string, optional, none|scrap_excess|invalid_sample|duplicate

## DowntimeReason

- downtime_reason_id: string, required, unique, format DT-0001
- reason_code: string, required, unique, MATERIAL|SETUP|CHANGEOVER|MECHANICAL|ELECTRICAL|PLANNED_BREAK|QUALITY|UNKNOWN
- reason_name: string, required, free text
- is_planned: boolean, required
- default_duration_minutes: integer, required, >0

## OEEAggregate

- aggregate_id: string, required, unique, generated as OEE-<machine>-<shift>
- machine_id: string, required, FK to Machine.machine_id
- shift_id: string, required, FK to Shift.shift_id
- availability: float, required, ratio between 0 and 1
- performance: float, required, ratio between 0 and 1
- quality: float, required, ratio between 0 and 1
- oee: float, required, availability _ performance _ quality
- planned_minutes: integer, required, total shift minutes
- runtime_minutes: integer, required, actual active run minutes
- downtime_minutes: integer, required, downtime minutes from reasons

## Cardinality and lifecycle notes

- Plant:Lines = 1:N
- Plant:Machines = 1:N via Line
- Line:Machines = 1:N
- Machine:ProductionOrders = 1:N
- Shift:ProductionOrders = 1:N
- Product:ProductionOrders = 1:N
- ProductionOrder:StateEvent = 1:N
- ProductionOrder:ProductionCount = 1:N
- ProductionOrder:QualityInspection = 1:N
- StateEvent:DowntimeReason = N:1 via reason_code
- Machine:OEEAggregate = 1:N

All records keep immutable identifiers and event history is appended without overwriting prior state. Known anomaly cases are preserved with issue labels in the ground-truth records instead of mutating unrelated rows.
