#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random

DATA_DICTIONARY = {
    "Plant": {
        "plant_id": {"type": "string", "required": True, "allowed_values": "PLT-####", "units": "n/a", "unique": True, "validation": "Primary key; pattern PLT-0001"},
        "plant_name": {"type": "string", "required": True, "allowed_values": "Free text", "units": "n/a", "unique": False, "validation": "Must not be empty"},
        "country": {"type": "string", "required": True, "allowed_values": "ISO country code", "units": "n/a", "unique": False, "validation": "Reference valid ISO 3166-1 alpha-2 code"},
        "timezone": {"type": "string", "required": True, "allowed_values": "UTC±HH:MM", "units": "timezone", "unique": False, "validation": "Must match offset format"},
        "status": {"type": "string", "required": True, "allowed_values": "active|inactive|maintenance", "units": "n/a", "unique": False, "validation": "Enum constrained"},
    },
    "Line": {
        "line_id": {"type": "string", "required": True, "allowed_values": "LIN-####", "units": "n/a", "unique": True, "validation": "Primary key; pattern LIN-0001"},
        "plant_id": {"type": "string", "required": True, "allowed_values": "Plant.plant_id", "units": "n/a", "unique": False, "validation": "FK to Plant"},
        "line_name": {"type": "string", "required": True, "allowed_values": "Free text", "units": "n/a", "unique": False, "validation": "Must not be empty"},
        "line_type": {"type": "string", "required": True, "allowed_values": "packaging|assembly|forming|machining|finishing", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "status": {"type": "string", "required": True, "allowed_values": "active|paused|maintenance", "units": "n/a", "unique": False, "validation": "Enum constrained"},
    },
    "Machine": {
        "machine_id": {"type": "string", "required": True, "allowed_values": "MCH-####", "units": "n/a", "unique": True, "validation": "Primary key; pattern MCH-0001"},
        "line_id": {"type": "string", "required": True, "allowed_values": "Line.line_id", "units": "n/a", "unique": False, "validation": "FK to Line"},
        "machine_name": {"type": "string", "required": True, "allowed_values": "Free text", "units": "n/a", "unique": False, "validation": "Must not be empty"},
        "machine_class": {"type": "string", "required": True, "allowed_values": "press|mixer|labeler|injector|packer|tester", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "ideal_cycle_seconds": {"type": "integer", "required": True, "allowed_values": ">0", "units": "seconds", "unique": False, "validation": "Positive integer; defaults to product-specific override"},
        "status": {"type": "string", "required": True, "allowed_values": "available|down|maintenance|offline", "units": "n/a", "unique": False, "validation": "Enum constrained"},
    },
    "Shift": {
        "shift_id": {"type": "string", "required": True, "allowed_values": "SHIFT-YYYY-MM-DD-A", "units": "n/a", "unique": True, "validation": "Primary key; deterministic pattern"},
        "shift_date": {"type": "date", "required": True, "allowed_values": "YYYY-MM-DD", "units": "date", "unique": False, "validation": "Date between 2026-01-01 and 2026-03-31"},
        "shift_code": {"type": "string", "required": True, "allowed_values": "A|B|C", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "start_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "Start is before end_ts"},
        "end_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "End is after start_ts"},
        "planned_break_minutes": {"type": "integer", "required": True, "allowed_values": "0-120", "units": "minutes", "unique": False, "validation": "Planned break cannot exceed shift length"},
    },
    "Product": {
        "product_id": {"type": "string", "required": True, "allowed_values": "PRD-####", "units": "n/a", "unique": True, "validation": "Primary key; pattern PRD-0001"},
        "product_name": {"type": "string", "required": True, "allowed_values": "Free text", "units": "n/a", "unique": False, "validation": "Must not be empty"},
        "family": {"type": "string", "required": True, "allowed_values": "SKU family", "units": "n/a", "unique": False, "validation": "Must not be empty"},
        "ideal_cycle_seconds": {"type": "integer", "required": True, "allowed_values": ">0", "units": "seconds/unit", "unique": False, "validation": "Positive integer"},
        "uom": {"type": "string", "required": True, "allowed_values": "pcs|kg|box", "units": "n/a", "unique": False, "validation": "Enum constrained"},
    },
    "ProductionOrder": {
        "production_order_id": {"type": "string", "required": True, "allowed_values": "PO-YYYY-######", "units": "n/a", "unique": True, "validation": "Primary key; pattern PO-2026-000001"},
        "machine_id": {"type": "string", "required": True, "allowed_values": "Machine.machine_id", "units": "n/a", "unique": False, "validation": "FK to Machine"},
        "product_id": {"type": "string", "required": True, "allowed_values": "Product.product_id", "units": "n/a", "unique": False, "validation": "FK to Product"},
        "shift_id": {"type": "string", "required": True, "allowed_values": "Shift.shift_id", "units": "n/a", "unique": False, "validation": "FK to Shift"},
        "planned_qty": {"type": "integer", "required": True, "allowed_values": ">0", "units": "pieces", "unique": False, "validation": "Positive integer"},
        "actual_qty": {"type": "integer", "required": False, "allowed_values": ">=0", "units": "pieces", "unique": False, "validation": "Derived from count records"},
        "status": {"type": "string", "required": True, "allowed_values": "planned|running|complete|held|cancelled", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "start_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "Start is before end_ts"},
        "end_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "End is after start_ts"},
    },
    "StateEvent": {
        "state_event_id": {"type": "string", "required": True, "allowed_values": "EVT-MCH-####-######", "units": "n/a", "unique": True, "validation": "Primary key; deterministic event ID"},
        "machine_id": {"type": "string", "required": True, "allowed_values": "Machine.machine_id", "units": "n/a", "unique": False, "validation": "FK to Machine"},
        "shift_id": {"type": "string", "required": True, "allowed_values": "Shift.shift_id", "units": "n/a", "unique": False, "validation": "FK to Shift"},
        "production_order_id": {"type": "string", "required": False, "allowed_values": "ProductionOrder.production_order_id", "units": "n/a", "unique": False, "validation": "Nullable only when machine is offline/idle"},
        "state_from": {"type": "string", "required": False, "allowed_values": "IDLE|RUN|DOWN|SETUP|BREAK|OFFLINE|MAINTENANCE", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "state_to": {"type": "string", "required": True, "allowed_values": "IDLE|RUN|DOWN|SETUP|BREAK|OFFLINE|MAINTENANCE", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "event_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "Must fall within shift start/end"},
        "duration_seconds": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "seconds", "unique": False, "validation": "Non-negative integer"},
        "reason_code": {"type": "string", "required": False, "allowed_values": "DowntimeReason.reason_code", "units": "n/a", "unique": False, "validation": "Required for DOWN/BREAK states"},
        "is_planned": {"type": "boolean", "required": False, "allowed_values": "true|false", "units": "n/a", "unique": False, "validation": "Set for planned breaks and changeovers"},
        "anomaly_flag": {"type": "string", "required": False, "allowed_values": "none|overlap|downtime_overlap|count_decrease|scrap_excess|wrong_cycle_time", "units": "n/a", "unique": False, "validation": "Persistent issue label for known exceptions"},
    },
    "ProductionCount": {
        "count_id": {"type": "string", "required": True, "allowed_values": "CNT-PO-######", "units": "n/a", "unique": True, "validation": "Primary key; deterministic format"},
        "production_order_id": {"type": "string", "required": True, "allowed_values": "ProductionOrder.production_order_id", "units": "n/a", "unique": False, "validation": "FK to ProductionOrder"},
        "machine_id": {"type": "string", "required": True, "allowed_values": "Machine.machine_id", "units": "n/a", "unique": False, "validation": "FK to Machine"},
        "product_id": {"type": "string", "required": True, "allowed_values": "Product.product_id", "units": "n/a", "unique": False, "validation": "FK to Product"},
        "shift_id": {"type": "string", "required": True, "allowed_values": "Shift.shift_id", "units": "n/a", "unique": False, "validation": "FK to Shift"},
        "count_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "Timestamp within shift window"},
        "count_type": {"type": "string", "required": True, "allowed_values": "good|scrap|rework|correction", "units": "n/a", "unique": False, "validation": "Enum constrained"},
        "quantity": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "pieces", "unique": False, "validation": "Positive for non-zero record"},
        "correction_flag": {"type": "boolean", "required": True, "allowed_values": "true|false", "units": "n/a", "unique": False, "validation": "Tracks count correction events explicitly"},
        "source_state_event_id": {"type": "string", "required": False, "allowed_values": "StateEvent.state_event_id", "units": "n/a", "unique": False, "validation": "FK to state event when tied to a state transition"},
    },
    "QualityInspection": {
        "inspection_id": {"type": "string", "required": True, "allowed_values": "QC-YYYY-######", "units": "n/a", "unique": True, "validation": "Primary key; pattern QC-2026-000001"},
        "production_order_id": {"type": "string", "required": True, "allowed_values": "ProductionOrder.production_order_id", "units": "n/a", "unique": False, "validation": "FK to ProductionOrder"},
        "machine_id": {"type": "string", "required": True, "allowed_values": "Machine.machine_id", "units": "n/a", "unique": False, "validation": "FK to Machine"},
        "product_id": {"type": "string", "required": True, "allowed_values": "Product.product_id", "units": "n/a", "unique": False, "validation": "FK to Product"},
        "shift_id": {"type": "string", "required": True, "allowed_values": "Shift.shift_id", "units": "n/a", "unique": False, "validation": "FK to Shift"},
        "inspection_ts": {"type": "datetime", "required": True, "allowed_values": "ISO timestamp", "units": "datetime", "unique": False, "validation": "Within shift"},
        "sample_qty": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "pieces", "unique": False, "validation": "Positive integer"},
        "good_qty": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "pieces", "unique": False, "validation": "good_qty <= sample_qty"},
        "scrap_qty": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "pieces", "unique": False, "validation": "scrap_qty <= sample_qty"},
        "rework_qty": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "pieces", "unique": False, "validation": "rework_qty <= sample_qty"},
        "pass_flag": {"type": "boolean", "required": True, "allowed_values": "true|false", "units": "n/a", "unique": False, "validation": "True if good_qty >= 0.95*sample_qty"},
        "defect_code": {"type": "string", "required": False, "allowed_values": "D001|D015|D033|D041|D099|NONE", "units": "n/a", "unique": False, "validation": "Optional defect reason"},
        "anomaly_flag": {"type": "string", "required": False, "allowed_values": "none|scrap_excess|invalid_sample|duplicate", "units": "n/a", "unique": False, "validation": "Known quality exceptions"},
    },
    "DowntimeReason": {
        "downtime_reason_id": {"type": "string", "required": True, "allowed_values": "DT-####", "units": "n/a", "unique": True, "validation": "Primary key; pattern DT-0001"},
        "reason_code": {"type": "string", "required": True, "allowed_values": "MATERIAL|SETUP|CHANGEOVER|MECHANICAL|ELECTRICAL|PLANNED_BREAK|QUALITY|UNKNOWN", "units": "n/a", "unique": True, "validation": "Unique code"},
        "reason_name": {"type": "string", "required": True, "allowed_values": "Free text", "units": "n/a", "unique": False, "validation": "Must not be empty"},
        "is_planned": {"type": "boolean", "required": True, "allowed_values": "true|false", "units": "n/a", "unique": False, "validation": "Explicit planned downtime flag"},
        "default_duration_minutes": {"type": "integer", "required": True, "allowed_values": ">0", "units": "minutes", "unique": False, "validation": "Positive integer"},
    },
    "OEEAggregate": {
        "aggregate_id": {"type": "string", "required": True, "allowed_values": "OEE-<machine>-<shift>-####", "units": "n/a", "unique": True, "validation": "Primary key"},
        "machine_id": {"type": "string", "required": True, "allowed_values": "Machine.machine_id", "units": "n/a", "unique": False, "validation": "FK to Machine"},
        "shift_id": {"type": "string", "required": True, "allowed_values": "Shift.shift_id", "units": "n/a", "unique": False, "validation": "FK to Shift"},
        "availability": {"type": "float", "required": True, "allowed_values": "0..1 or 0..100%", "units": "ratio", "unique": False, "validation": "Availability = operating / planned"},
        "performance": {"type": "float", "required": True, "allowed_values": "0..1 or 0..100%", "units": "ratio", "unique": False, "validation": "Performance = actual / ideal"},
        "quality": {"type": "float", "required": True, "allowed_values": "0..1 or 0..100%", "units": "ratio", "unique": False, "validation": "Quality = good / total"},
        "oee": {"type": "float", "required": True, "allowed_values": "0..1 or 0..100%", "units": "ratio", "unique": False, "validation": "OEE = availability * performance * quality"},
        "planned_minutes": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "minutes", "unique": False, "validation": "Total shift minutes"},
        "runtime_minutes": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "minutes", "unique": False, "validation": "Actual run minutes"},
        "downtime_minutes": {"type": "integer", "required": True, "allowed_values": ">=0", "units": "minutes", "unique": False, "validation": "Downtime minutes from reasons"},
    }
}


def iso(dt):
    return dt.isoformat(timespec="seconds")


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_shift_calendar(start_date, number_of_days=90):
    shifts = []
    for offset in range(number_of_days):
        current_day = start_date + timedelta(days=offset)
        for shift_code, start_hour in [("A", 6), ("B", 14), ("C", 22)]:
            start_dt = datetime.combine(current_day, datetime.min.time()) + timedelta(hours=start_hour)
            end_dt = start_dt + timedelta(hours=8)
            shifts.append({
                "shift_id": f"SHIFT-{current_day.isoformat()}-{shift_code}",
                "shift_date": current_day.isoformat(),
                "shift_code": shift_code,
                "start_ts": iso(start_dt),
                "end_ts": iso(end_dt),
                "planned_break_minutes": 30,
            })
    return shifts


def build_factory_master():
    plants = [{"plant_id": "PLT-0001", "plant_name": "North Plant", "country": "US", "timezone": "UTC-05:00", "status": "active"}]
    lines = []
    line_names = ["L01 Forming", "L02 Blending", "L03 Fill", "L04 Pack", "L05 Quality"]
    line_types = ["forming", "machining", "packaging", "assembly", "finishing"]
    for idx, (name, type_name) in enumerate(zip(line_names, line_types), start=1):
        lines.append({"line_id": f"LIN-{idx:04d}", "plant_id": "PLT-0001", "line_name": name, "line_type": type_name, "status": "active"})
    machines = []
    machine_class_cycle = ["press", "mixer", "labeler", "injector", "packer", "tester"]
    machine_index = 1
    for line in lines:
        for offset in range(1, 7):
            machine_id = f"MCH-{machine_index:04d}"
            machines.append({
                "machine_id": machine_id,
                "line_id": line["line_id"],
                "machine_name": f"{line['line_name']}-{offset:02d}",
                "machine_class": machine_class_cycle[(machine_index - 1) % len(machine_class_cycle)],
                "ideal_cycle_seconds": 20 + (machine_index % 16),
                "status": "available",
            })
            machine_index += 1
    return plants, lines, machines


def build_products():
    product_specs = [
        ("PRD-0001", "Alpha Bottle", "BOTTLE", 18, "pcs"),
        ("PRD-0002", "Beta Cap", "CAP", 15, "pcs"),
        ("PRD-0003", "Gamma Syrup", "LIQUID", 22, "pcs"),
        ("PRD-0004", "Delta Blister", "PACK", 28, "pcs"),
        ("PRD-0005", "Epsilon Tube", "TUBE", 20, "pcs"),
        ("PRD-0006", "Zeta Tray", "TRAY", 30, "pcs"),
        ("PRD-0007", "Eta Pouch", "POUCH", 17, "pcs"),
        ("PRD-0008", "Theta Carton", "CARTON", 26, "pcs"),
        ("PRD-0009", "Iota Seal", "SEAL", 12, "pcs"),
        ("PRD-0010", "Kappa Label", "LABEL", 14, "pcs"),
        ("PRD-0011", "Lambda Jar", "JAR", 24, "pcs"),
        ("PRD-0012", "Mu Bag", "BAG", 19, "pcs"),
        ("PRD-0013", "Nu Box", "BOX", 29, "pcs"),
        ("PRD-0014", "Xi Sleeve", "SLEEVE", 16, "pcs"),
        ("PRD-0015", "Omicron Case", "CASE", 32, "pcs"),
        ("PRD-0016", "Pi Wrapper", "WRAPPER", 21, "pcs"),
        ("PRD-0017", "Rho Canister", "CANISTER", 27, "pcs"),
        ("PRD-0018", "Sigma Insert", "INSERT", 13, "pcs"),
        ("PRD-0019", "Tau Filter", "FILTER", 23, "pcs"),
        ("PRD-0020", "Upsilon Beam", "BEAM", 31, "pcs"),
    ]
    products = []
    for product_id, name, family, cycle_seconds, unit in product_specs:
        products.append({"product_id": product_id, "product_name": name, "family": family, "ideal_cycle_seconds": cycle_seconds, "uom": unit})
    return products


def build_downtime_reasons():
    return [
        {"downtime_reason_id": "DT-0001", "reason_code": "MATERIAL", "reason_name": "Material shortage", "is_planned": False, "default_duration_minutes": 18},
        {"downtime_reason_id": "DT-0002", "reason_code": "SETUP", "reason_name": "Setup and adjustment", "is_planned": True, "default_duration_minutes": 22},
        {"downtime_reason_id": "DT-0003", "reason_code": "CHANGEOVER", "reason_name": "Changeover", "is_planned": True, "default_duration_minutes": 26},
        {"downtime_reason_id": "DT-0004", "reason_code": "MECHANICAL", "reason_name": "Mechanical fault", "is_planned": False, "default_duration_minutes": 39},
        {"downtime_reason_id": "DT-0005", "reason_code": "ELECTRICAL", "reason_name": "Electrical issue", "is_planned": False, "default_duration_minutes": 31},
        {"downtime_reason_id": "DT-0006", "reason_code": "PLANNED_BREAK", "reason_name": "Planned break", "is_planned": True, "default_duration_minutes": 30},
        {"downtime_reason_id": "DT-0007", "reason_code": "QUALITY", "reason_name": "Quality hold", "is_planned": False, "default_duration_minutes": 20},
        {"downtime_reason_id": "DT-0008", "reason_code": "UNKNOWN", "reason_name": "Unknown interruption", "is_planned": False, "default_duration_minutes": 12},
    ]


def generate_dataset(seed=20261022, scale=1.0, output_dir=None):
    rng = Random(seed)
    plants, lines, machines = build_factory_master()
    products = build_products()
    shifts = build_shift_calendar(datetime(2026, 1, 1), number_of_days=90)
    downtime_reasons = build_downtime_reasons()
    reason_lookup = {item["reason_code"]: item for item in downtime_reasons}

    orders = []
    state_events = []
    production_counts = []
    quality_inspections = []
    oee_aggregate = []

    event_counter = 1
    count_counter = 1
    inspection_counter = 1
    order_counter = 1
    product_map = {p["product_id"]: p for p in products}
    machine_map = {m["machine_id"]: m for m in machines}

    directed_state_sequence = ["IDLE", "RUN", "SETUP", "RUN", "DOWN", "RUN", "BREAK", "RUN", "IDLE", "RUN", "DOWN", "RUN"]

    for shift in shifts:
        shift_start = datetime.fromisoformat(shift["start_ts"])
        for machine in machines:
            product = products[(machine_index := (machines.index(machine) + order_counter)) % len(products)]
            product_id = product["product_id"]
            order_id = f"PO-{shift_start.year}-{order_counter:06d}"
            planned_qty = 350 + int(rng.random() * 1800)
            start_dt = shift_start + timedelta(minutes=15 + rng.random() * 20)
            end_dt = start_dt + timedelta(minutes=200 + rng.random() * 160)
            order = {
                "production_order_id": order_id,
                "machine_id": machine["machine_id"],
                "product_id": product_id,
                "shift_id": shift["shift_id"],
                "planned_qty": planned_qty,
                "actual_qty": None,
                "status": "complete",
                "start_ts": iso(start_dt),
                "end_ts": iso(end_dt),
            }
            orders.append(order)

            current_ts = start_dt
            for state_index, state_to in enumerate(directed_state_sequence):
                state_from = directed_state_sequence[state_index - 1] if state_index > 0 else "IDLE"
                if state_to == "RUN":
                    duration_seconds = 260 + int(rng.random() * 700)
                elif state_to == "SETUP":
                    duration_seconds = 180 + int(rng.random() * 250)
                elif state_to == "DOWN":
                    duration_seconds = 240 + int(rng.random() * 620)
                elif state_to == "BREAK":
                    duration_seconds = 220 + int(rng.random() * 540)
                else:
                    duration_seconds = 120 + int(rng.random() * 180)

                reason_code = None
                is_planned = False
                anomaly_flag = "none"
                if state_to in {"DOWN", "BREAK"}:
                    reason_code = rng.choice(list(reason_lookup.keys()))
                    is_planned = reason_lookup[reason_code]["is_planned"]
                    if state_to == "BREAK" and rng.random() < 0.08:
                        anomaly_flag = "downtime_overlap"
                if rng.random() < 0.01:
                    anomaly_flag = "overlap"

                state_events.append({
                    "state_event_id": f"EVT-{machine['machine_id']}-{event_counter:06d}",
                    "machine_id": machine["machine_id"],
                    "shift_id": shift["shift_id"],
                    "production_order_id": order_id,
                    "state_from": state_from,
                    "state_to": state_to,
                    "event_ts": iso(current_ts),
                    "duration_seconds": duration_seconds,
                    "reason_code": reason_code,
                    "is_planned": is_planned,
                    "anomaly_flag": anomaly_flag,
                })
                event_counter += 1
                current_ts += timedelta(seconds=duration_seconds)

            order_good = 0
            order_scrap = 0
            order_rework = 0
            for count_index in range(1, 42):
                count_type = rng.choices(["good", "scrap", "rework"], weights=[72, 18, 10], k=1)[0]
                quantity = 12 + int(rng.random() * 90)
                if count_type == "good":
                    order_good += quantity
                elif count_type == "scrap":
                    order_scrap += quantity
                else:
                    order_rework += quantity
                production_counts.append({
                    "count_id": f"CNT-{order_id}-{count_counter:06d}",
                    "production_order_id": order_id,
                    "machine_id": machine["machine_id"],
                    "product_id": product_id,
                    "shift_id": shift["shift_id"],
                    "count_ts": iso(start_dt + timedelta(minutes=20 + count_index * 6 + rng.random() * 8)),
                    "count_type": count_type,
                    "quantity": quantity,
                    "correction_flag": False,
                    "source_state_event_id": state_events[-1]["state_event_id"],
                })
                count_counter += 1

            if rng.random() < 0.07:
                production_counts.append({
                    "count_id": f"CNT-{order_id}-{count_counter:06d}",
                    "production_order_id": order_id,
                    "machine_id": machine["machine_id"],
                    "product_id": product_id,
                    "shift_id": shift["shift_id"],
                    "count_ts": iso(start_dt + timedelta(minutes=120)),
                    "count_type": "correction",
                    "quantity": max(0, order_good - 25),
                    "correction_flag": True,
                    "source_state_event_id": state_events[-1]["state_event_id"],
                })
                count_counter += 1

            for _ in range(2):
                sample_qty = 65 + int(rng.random() * 120)
                scrap_qty = int(rng.random() * 30)
                rework_qty = int(rng.random() * 18)
                good_qty = max(0, sample_qty - scrap_qty - rework_qty)
                quality_inspections.append({
                    "inspection_id": f"QC-{start_dt.year}-{inspection_counter:06d}",
                    "production_order_id": order_id,
                    "machine_id": machine["machine_id"],
                    "product_id": product_id,
                    "shift_id": shift["shift_id"],
                    "inspection_ts": iso(start_dt + timedelta(minutes=40 + rng.random() * 170)),
                    "sample_qty": sample_qty,
                    "good_qty": good_qty,
                    "scrap_qty": scrap_qty,
                    "rework_qty": rework_qty,
                    "pass_flag": good_qty >= sample_qty * 0.94,
                    "defect_code": rng.choice(["D001", "D015", "D033", "D041", "D099", "NONE"]),
                    "anomaly_flag": "none",
                })
                inspection_counter += 1

            if rng.random() < 0.04:
                quality_inspections[-1]["anomaly_flag"] = "scrap_excess"
                quality_inspections[-1]["scrap_qty"] = quality_inspections[-1]["sample_qty"] + 3

            order["actual_qty"] = order_good + order_scrap + order_rework
            planned_minutes = int((datetime.fromisoformat(shift["end_ts"]) - datetime.fromisoformat(shift["start_ts"])).total_seconds() / 60)
            run_seconds = sum(evt["duration_seconds"] for evt in state_events if evt["production_order_id"] == order_id and evt["state_to"] == "RUN")
            downtime_seconds = sum(evt["duration_seconds"] for evt in state_events if evt["production_order_id"] == order_id and evt["state_to"] in {"DOWN", "BREAK", "SETUP"})
            availability = max(0.0, min(1.0, (planned_minutes * 60 - downtime_seconds) / (planned_minutes * 60)))
            actual_units = max(1, order_good)
            ideal_units = max(1.0, run_seconds / product["ideal_cycle_seconds"])
            performance = max(0.0, min(1.0, actual_units / ideal_units))
            total_quality = max(1, order_good + order_scrap + order_rework)
            quality_ratio = order_good / total_quality
            availability_rounded = round(availability, 6)
            performance_rounded = round(performance, 6)
            quality_rounded = round(quality_ratio, 6)
            oee_value = round(availability_rounded * performance_rounded * quality_rounded, 6)
            oee_aggregate.append({
                "aggregate_id": f"OEE-{machine['machine_id']}-{shift['shift_id']}",
                "machine_id": machine["machine_id"],
                "shift_id": shift["shift_id"],
                "availability": availability_rounded,
                "performance": performance_rounded,
                "quality": quality_rounded,
                "oee": oee_value,
                "planned_minutes": planned_minutes,
                "runtime_minutes": int(run_seconds / 60),
                "downtime_minutes": int(downtime_seconds / 60),
            })
            order_counter += 1

    target_state_events = max(10000, int(round(100_000 * scale)))
    target_count_records = max(10000, int(round(330_000 * scale)))
    target_quality_records = max(10000, int(round(170_000 * scale)))

    while len(state_events) < target_state_events:
        order = orders[len(state_events) % len(orders)]
        machine = machine_map[order["machine_id"]]
        state_events.append({
            "state_event_id": f"EVT-{machine['machine_id']}-{event_counter:06d}",
            "machine_id": machine["machine_id"],
            "shift_id": order["shift_id"],
            "production_order_id": order["production_order_id"],
            "state_from": "RUN",
            "state_to": "IDLE",
            "event_ts": iso(datetime.fromisoformat(order["start_ts"]) + timedelta(minutes=20 + len(state_events) % 120)),
            "duration_seconds": 90 + len(state_events) % 90,
            "reason_code": None,
            "is_planned": False,
            "anomaly_flag": "none",
        })
        event_counter += 1

    while len(production_counts) < target_count_records:
        order = orders[len(production_counts) % len(orders)]
        machine = machine_map[order["machine_id"]]
        count_type = "good" if len(production_counts) % 4 else "scrap"
        production_counts.append({
            "count_id": f"CNT-{order['production_order_id']}-{count_counter:06d}",
            "production_order_id": order["production_order_id"],
            "machine_id": machine["machine_id"],
            "product_id": order["product_id"],
            "shift_id": order["shift_id"],
            "count_ts": iso(datetime.fromisoformat(order["start_ts"]) + timedelta(minutes=20 + len(production_counts) % 90)),
            "count_type": count_type,
            "quantity": 10 + (len(production_counts) % 120),
            "correction_flag": False,
            "source_state_event_id": state_events[(len(production_counts) + 1) % len(state_events)]["state_event_id"],
        })
        count_counter += 1

    while len(quality_inspections) < target_quality_records:
        order = orders[len(quality_inspections) % len(orders)]
        machine = machine_map[order["machine_id"]]
        sample_qty = 50 + (len(quality_inspections) % 120)
        scrap_qty = (len(quality_inspections) % 20)
        rework_qty = (len(quality_inspections) % 12)
        good_qty = max(0, sample_qty - scrap_qty - rework_qty)
        quality_inspections.append({
            "inspection_id": f"QC-{datetime.fromisoformat(order['start_ts']).year}-{inspection_counter:06d}",
            "production_order_id": order["production_order_id"],
            "machine_id": machine["machine_id"],
            "product_id": order["product_id"],
            "shift_id": order["shift_id"],
            "inspection_ts": iso(datetime.fromisoformat(order["start_ts"]) + timedelta(minutes=30 + len(quality_inspections) % 180)),
            "sample_qty": sample_qty,
            "good_qty": good_qty,
            "scrap_qty": scrap_qty,
            "rework_qty": rework_qty,
            "pass_flag": good_qty >= sample_qty * 0.94,
            "defect_code": "NONE" if len(quality_inspections) % 5 else "D001",
            "anomaly_flag": "none",
        })
        inspection_counter += 1

    # Deliberate exceptions with explicit labels.
    if state_events:
        state_events[0]["anomaly_flag"] = "overlap"
        state_events[1]["anomaly_flag"] = "overlap"
    if production_counts:
        production_counts[0]["quantity"] = max(0, production_counts[0]["quantity"] - 12)
        production_counts[0]["count_type"] = "good"
    if quality_inspections:
        quality_inspections[0]["scrap_qty"] = quality_inspections[0]["sample_qty"] + 2
        quality_inspections[0]["anomaly_flag"] = "scrap_excess"
    if products:
        products[0]["ideal_cycle_seconds"] = 7

    dataset = {
        "plants": plants,
        "lines": lines,
        "machines": machines,
        "shifts": shifts,
        "products": products,
        "production_orders": orders,
        "state_events": state_events,
        "production_counts": production_counts,
        "quality_inspections": quality_inspections,
        "downtime_reasons": downtime_reasons,
        "oee_aggregate": oee_aggregate,
        "ground_truth": [
            {"issue_type": "overlapping_machine_states", "entity": "state_events", "record_ids": [state_events[0]["state_event_id"], state_events[1]["state_event_id"]], "expected_decision": "Keep both events and flag overlap_exception", "details": "State transitions overlap in time."},
            {"issue_type": "count_decrease_without_correction", "entity": "production_counts", "record_ids": [production_counts[0]["count_id"]], "expected_decision": "Keep raw count and label for reconciliation review.", "details": "A count decreased without a correction event."},
            {"issue_type": "scrap_exceeds_total", "entity": "quality_inspections", "record_ids": [quality_inspections[0]["inspection_id"]], "expected_decision": "Keep record and label anomaly while preserving raw totals.", "details": "Scrap exceeds sample quantity."},
            {"issue_type": "wrong_ideal_cycle_time", "entity": "products", "record_ids": [products[0]["product_id"]], "expected_decision": "Retain product master; flag cycle_time_review.", "details": "Machine-level cycle time differs from expected product target."},
            {"issue_type": "downtime_overlaps_planned_break", "entity": "state_events", "record_ids": [state_events[-1]["state_event_id"]], "expected_decision": "Retain downtime event and keep planned break explicit.", "details": "Unplanned downtime overlaps planned break."},
        ],
    }

    if output_dir is not None:
        save_dataset(dataset, output_dir)
    return dataset


def save_dataset(dataset, output_dir):
    output_path = Path(output_dir)
    ensure_dir(output_path)
    ensure_dir(output_path / "csv")
    ensure_dir(output_path / "json")

    feature_tables = {name: rows for name, rows in dataset.items() if name != "ground_truth"}

    for table_name, rows in feature_tables.items():
        csv_path = output_path / "csv" / f"{table_name}.csv"
        if rows:
            fieldnames = list(rows[0].keys())
            with open(csv_path, "w", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        else:
            csv_path.write_text("")

    ground_truth_rows = dataset.get("ground_truth", [])
    if ground_truth_rows:
        fieldnames = list(ground_truth_rows[0].keys())
        with open(output_path / "csv" / "ground_truth.csv", "w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in ground_truth_rows:
                writer.writerow(row)
    else:
        (output_path / "csv" / "ground_truth.csv").write_text("")

    with open(output_path / "json" / "dataset.json", "w") as handle:
        json.dump(feature_tables, handle, indent=2)
    with open(output_path / "json" / "ground_truth.json", "w") as handle:
        json.dump(ground_truth_rows, handle, indent=2)

    insert_lines = []
    for table_name, rows in feature_tables.items():
        if not rows:
            continue
        columns = list(rows[0].keys())
        insert_lines.append(f"CREATE TABLE IF NOT EXISTS \"{table_name}\" ({', '.join(f'\"{c}\" TEXT' for c in columns)});")
        for row in rows:
            values = []
            for col in columns:
                value = row.get(col)
                if value is None:
                    values.append("NULL")
                elif isinstance(value, bool):
                    values.append("TRUE" if value else "FALSE")
                elif isinstance(value, (int, float)):
                    values.append(str(value))
                else:
                    values.append("'" + str(value).replace("'", "''") + "'")
            insert_lines.append(f"INSERT INTO \"{table_name}\" ({', '.join(f'\"{c}\"' for c in columns)}) VALUES ({', '.join(values)});")
    with open(output_path / "seed.sql", "w") as handle:
        handle.write("\n".join(insert_lines))

    manifest = {
        "seed": 20261022,
        "generator": "generator.py",
        "tables": sorted(feature_tables),
        "generated_at": iso(datetime.now(timezone.utc)),
        "notes": "Synthetic manufacturing OEE dataset for forecast, state, count, and quality validation."
    }
    with open(output_path / "source_manifest.json", "w") as handle:
        json.dump(manifest, handle, indent=2)


def validate_dataset(dataset):
    summary = []
    for table_name, rows in dataset.items():
        if table_name == "ground_truth":
            continue
        if not rows:
            continue
        pk_field = {
            "plants": "plant_id",
            "lines": "line_id",
            "machines": "machine_id",
            "shifts": "shift_id",
            "products": "product_id",
            "production_orders": "production_order_id",
            "state_events": "state_event_id",
            "production_counts": "count_id",
            "quality_inspections": "inspection_id",
            "downtime_reasons": "downtime_reason_id",
            "oee_aggregate": "aggregate_id",
        }.get(table_name)
        if pk_field:
            key_set = {row[pk_field] for row in rows}
            summary.append({"check": f"{table_name}: primary key uniqueness", "result": "pass" if len(key_set) == len(rows) else "fail"})

    for row in dataset["state_events"]:
        if row["state_to"] not in {"IDLE", "RUN", "DOWN", "SETUP", "BREAK", "OFFLINE", "MAINTENANCE"}:
            summary.append({"check": "state_event enum validation", "result": "fail"})
            break
    else:
        summary.append({"check": "state_event enum validation", "result": "pass"})

    arithmetic_fail = False
    for row in dataset["oee_aggregate"]:
        calc = row["availability"] * row["performance"] * row["quality"]
        if abs(calc - row["oee"]) > 0.000001:
            arithmetic_fail = True
    summary.append({"check": "OEE arithmetic reconciliation", "result": "fail" if arithmetic_fail else "pass"})

    return {"row_counts": {name: len(rows) for name, rows in dataset.items() if name != "ground_truth"}, "summary": summary}


def write_validation_summary(output_dir, validation):
    path = Path(output_dir) / "validation_summary.json"
    with open(path, "w") as handle:
        json.dump(validation, handle, indent=2)


def run_reproducibility_check(output_dir, seed=20261022, scale=1.0):
    first = Path(output_dir) / "repro_run_1"
    second = Path(output_dir) / "repro_run_2"
    dataset1 = generate_dataset(seed=seed, scale=scale, output_dir=str(first))
    dataset2 = generate_dataset(seed=seed, scale=scale, output_dir=str(second))
    checksums = {}
    for table_name in ["plants", "lines", "machines", "shifts", "products", "production_orders", "state_events", "production_counts", "quality_inspections", "downtime_reasons", "oee_aggregate"]:
        first_csv = first / "csv" / f"{table_name}.csv"
        second_csv = second / "csv" / f"{table_name}.csv"
        h1 = sha256_file(first_csv)
        h2 = sha256_file(second_csv)
        checksums[table_name] = {"sha256_run_1": h1, "sha256_run_2": h2, "identical": h1 == h2, "row_count_run_1": len(dataset1[table_name]), "row_count_run_2": len(dataset2[table_name])}
    summary = {"seed": seed, "scale": scale, "identical": all(value["identical"] for value in checksums.values()), "checksums": checksums}
    with open(Path(output_dir) / "reproducibility_summary.json", "w") as handle:
        json.dump(summary, handle, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Synthetic OEE dataset generator")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--output-dir", type=str, default="data")
    parser.add_argument("--repro-check", action="store_true")
    args = parser.parse_args()

    dataset = generate_dataset(seed=args.seed, scale=args.scale, output_dir=args.output_dir)
    validation = validate_dataset(dataset)
    write_validation_summary(args.output_dir, validation)
    if args.repro_check:
        repro = run_reproducibility_check(args.output_dir, seed=args.seed, scale=args.scale)
        print(json.dumps({"row_counts": validation["row_counts"], "reproducible": repro["identical"]}, indent=2))
    else:
        print(json.dumps({"row_counts": validation["row_counts"], "summary": validation["summary"]}, indent=2))


if __name__ == "__main__":
    main()
