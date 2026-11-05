from __future__ import annotations

import json
import shutil
from pathlib import Path

from filp_bach4popper.partitioning.partitioner import DatasetPartition


def write_partitions(
    dataset_name: str,
    partitions: list[DatasetPartition],
    strategy: str,
    random_seed: int,
    output_root: Path,
) -> Path:
    output_directory = (
        output_root
        / dataset_name
        / f"{strategy}_{len(partitions)}_seed_{random_seed}"
    )

    if output_directory.exists():
        shutil.rmtree(output_directory)

    output_directory.mkdir(parents=True)

    metadata = {
        "dataset": dataset_name,
        "strategy": strategy,
        "number_of_clients": len(partitions),
        "random_seed": random_seed,
        "clients": [],
    }

    for partition in partitions:
        client_directory = (
            output_directory
            / f"{dataset_name}_part{partition.client_id}"
        )

        client_directory.mkdir(parents=True)

        _write_examples(
            client_directory / "exs.pl",
            partition,
        )

        _write_background_knowledge(
            client_directory / "bk.pl",
            partition,
        )

        (client_directory / "bias.pl").write_text(
            partition.bias,
            encoding="utf-8",
        )

        metadata["clients"].append(
            {
                "client_id": partition.client_id,
                "positive_examples": len(
                    partition.positive_examples
                ),
                "negative_examples": len(
                    partition.negative_examples
                ),
                "facts": len(partition.facts),
                "rules": len(partition.rules),
                "directory": client_directory.name,
            }
        )

    metadata_path = output_directory / "metadata.json"

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    return output_directory


def _write_examples(
    output_path: Path,
    partition: DatasetPartition,
) -> None:
    lines: list[str] = []

    for example in partition.positive_examples:
        lines.append(f"pos({example.identifier}).")

    for example in partition.negative_examples:
        lines.append(f"neg({example.identifier}).")

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_background_knowledge(
    output_path: Path,
    partition: DatasetPartition,
) -> None:
    statements = [
        fact.text
        for fact in partition.facts
    ]

    statements.extend(
        rule.text
        for rule in partition.rules
    )

    output_path.write_text(
        "\n\n".join(statements) + "\n",
        encoding="utf-8",
    )