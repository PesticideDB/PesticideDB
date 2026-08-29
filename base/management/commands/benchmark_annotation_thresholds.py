import itertools
import math
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError


DEFAULT_IDENTITIES = [20, 25, 30, 35, 40, 50, 70]
DEFAULT_DIAMOND_EVALUES = [1e-3, 1e-5, 1e-10, 1e-20]
DEFAULT_COVERAGES = [40, 50, 60, 70, 80]
DEFAULT_HMMER_EVALUES = [1e-3, 1e-5, 1e-10, 1e-20]
REQUIRED_COLUMNS = {
    "is_positive",
    "identity",
    "diamond_evalue",
    "query_coverage",
    "subject_coverage",
}


def parse_number_list(value, defaults):
    if not value:
        return defaults
    try:
        return [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise CommandError(f"Invalid numeric threshold list: {value}") from exc


def parse_boolean_series(series, column_name):
    true_values = {"1", "true", "yes", "y", "positive"}
    false_values = {"0", "false", "no", "n", "negative"}
    normalized = series.astype(str).str.strip().str.lower()
    unknown = normalized[~normalized.isin(true_values | false_values)]
    if not unknown.empty:
        values = ", ".join(sorted(unknown.unique()))
        raise CommandError(f"Invalid values in {column_name}: {values}")
    return normalized.isin(true_values)


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def calculate_metrics(truth, predicted):
    truth = truth.astype(bool)
    predicted = predicted.astype(bool)
    tp = int((truth & predicted).sum())
    fp = int((~truth & predicted).sum())
    tn = int((~truth & ~predicted).sum())
    fn = int((truth & ~predicted).sum())

    sensitivity = safe_ratio(tp, tp + fn)
    specificity = safe_ratio(tn, tn + fp)
    precision = safe_ratio(tp, tp + fp)
    f1 = safe_ratio(2 * precision * sensitivity, precision + sensitivity)
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = safe_ratio((tp * tn) - (fp * fn), denominator)

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "accuracy": safe_ratio(tp + tn, tp + fp + tn + fn),
        "false_positive_rate": safe_ratio(fp, fp + tn),
        "youden_j": sensitivity + specificity - 1,
        "mcc": mcc,
    }


class Command(BaseCommand):
    help = (
        "Sweep DIAMOND and optional HMMER thresholds over an independently labeled "
        "benchmark CSV and report classification metrics."
    )

    def add_arguments(self, parser):
        parser.add_argument("input_csv", type=Path)
        parser.add_argument(
            "--output",
            type=Path,
            default=Path("PBDB_annotation/benchmark/threshold_benchmark_results.csv"),
        )
        parser.add_argument("--identities", help="Comma-separated percent identities.")
        parser.add_argument("--diamond-evalues", help="Comma-separated DIAMOND E-values.")
        parser.add_argument("--coverages", help="Comma-separated query/subject coverages.")
        parser.add_argument("--hmmer-evalues", help="Comma-separated HMMER E-values.")

    def handle(self, *args, **options):
        input_path = options["input_csv"]
        output_path = options["output"]
        if not input_path.exists():
            raise CommandError(f"Benchmark CSV not found: {input_path}")

        data = pd.read_csv(input_path)
        missing = REQUIRED_COLUMNS - set(data.columns)
        if missing:
            raise CommandError(
                "Benchmark CSV is missing required columns: " + ", ".join(sorted(missing))
            )
        if data.empty:
            raise CommandError("Benchmark CSV contains no records.")

        data["is_positive"] = parse_boolean_series(data["is_positive"], "is_positive")
        numeric_columns = [
            "identity",
            "diamond_evalue",
            "query_coverage",
            "subject_coverage",
        ]
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        if data[numeric_columns].isna().any().any():
            raise CommandError(
                "Identity, DIAMOND E-value, and coverage columns must contain numbers."
            )

        has_hmmer = "hmmer_evalue" in data.columns
        if has_hmmer:
            data["hmmer_evalue"] = pd.to_numeric(data["hmmer_evalue"], errors="coerce")
        has_agreement = "family_agreement" in data.columns
        if has_agreement:
            data["family_agreement"] = parse_boolean_series(
                data["family_agreement"].fillna("no"),
                "family_agreement",
            )

        identities = parse_number_list(options["identities"], DEFAULT_IDENTITIES)
        diamond_evalues = parse_number_list(
            options["diamond_evalues"], DEFAULT_DIAMOND_EVALUES
        )
        coverages = parse_number_list(options["coverages"], DEFAULT_COVERAGES)
        hmmer_evalues = [None]
        if has_hmmer:
            hmmer_evalues.extend(
                parse_number_list(options["hmmer_evalues"], DEFAULT_HMMER_EVALUES)
            )

        rows = []
        diamond_combinations = itertools.product(
            identities,
            diamond_evalues,
            coverages,
            coverages,
        )
        for (
            identity,
            diamond_evalue,
            query_coverage,
            subject_coverage,
        ) in diamond_combinations:
            for hmmer_evalue in hmmer_evalues:
                agreement_options = (
                    [False, True]
                    if hmmer_evalue is not None and has_agreement
                    else [False]
                )
                for require_agreement in agreement_options:
                    predicted = (
                        (data["identity"] >= identity)
                        & (data["diamond_evalue"] <= diamond_evalue)
                        & (data["query_coverage"] >= query_coverage)
                        & (data["subject_coverage"] >= subject_coverage)
                    )
                    if hmmer_evalue is not None:
                        predicted &= data["hmmer_evalue"].notna()
                        predicted &= data["hmmer_evalue"] <= hmmer_evalue
                    if require_agreement:
                        predicted &= data["family_agreement"]

                    row = {
                        "identity_min": identity,
                        "diamond_evalue_max": diamond_evalue,
                        "query_coverage_min": query_coverage,
                        "subject_coverage_min": subject_coverage,
                        "hmmer_evalue_max": (
                            hmmer_evalue if hmmer_evalue is not None else ""
                        ),
                        "require_family_agreement": require_agreement,
                    }
                    row.update(calculate_metrics(data["is_positive"], predicted))
                    rows.append(row)

        results = pd.DataFrame(rows).sort_values(
            ["mcc", "f1", "youden_j", "sensitivity"],
            ascending=False,
        )
        metric_columns = [
            "sensitivity",
            "specificity",
            "precision",
            "f1",
            "accuracy",
            "false_positive_rate",
            "youden_j",
            "mcc",
        ]
        results[metric_columns] = results[metric_columns].round(4)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output_path, index=False)

        best = results.iloc[0]
        self.stdout.write(self.style.SUCCESS(
            f"Evaluated {len(results)} threshold combinations using {len(data)} records."
        ))
        self.stdout.write(f"Results: {output_path}")
        self.stdout.write(
            "Best by MCC: "
            f"identity >= {best['identity_min']:g}%, "
            f"DIAMOND E-value <= {best['diamond_evalue_max']:.1e}, "
            f"query coverage >= {best['query_coverage_min']:g}%, "
            f"subject coverage >= {best['subject_coverage_min']:g}%."
        )
        self.stdout.write(
            f"Sensitivity {best['sensitivity']:.3f}; "
            f"specificity {best['specificity']:.3f}; "
            f"precision {best['precision']:.3f}; "
            f"F1 {best['f1']:.3f}; MCC {best['mcc']:.3f}."
        )
