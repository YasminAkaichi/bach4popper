from __future__ import annotations

import random
from dataclasses import dataclass, field

from filp_bach4popper.partitioning.dataset import Dataset, Example, Fact, Rule


@dataclass
class DatasetPartition:
    client_id: int
    positive_examples: list[Example] = field(default_factory=list)
    negative_examples: list[Example] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    bias: str = ""


def partition_dataset(
    dataset: Dataset,
    number_of_clients: int,
    strategy: str,
    random_seed: int = 42,
) -> list[DatasetPartition]:
    if number_of_clients < 1:
        raise ValueError(
            "The number of clients must be at least 1."
        )

    if strategy not in {"iid", "non_iid"}:
        raise ValueError(
            "The partition strategy must be 'iid' or 'non_iid'."
        )

    if strategy == "iid":
        partitions = _partition_iid(
            dataset=dataset,
            number_of_clients=number_of_clients,
            random_seed=random_seed,
        )
    else:
        partitions = _partition_non_iid(
            dataset=dataset,
            number_of_clients=number_of_clients,
            random_seed=random_seed,
        )

    _attach_background_knowledge(
        dataset=dataset,
        partitions=partitions,
    )

    return partitions


def _partition_iid(
    dataset: Dataset,
    number_of_clients: int,
    random_seed: int,
) -> list[DatasetPartition]:
    random_generator = random.Random(random_seed)

    positive_examples = list(dataset.positive_examples)
    negative_examples = list(dataset.negative_examples)

    random_generator.shuffle(positive_examples)
    random_generator.shuffle(negative_examples)

    partitions = [
        DatasetPartition(
            client_id=client_id,
            bias=dataset.bias,
        )
        for client_id in range(1, number_of_clients + 1)
    ]

    for index, example in enumerate(positive_examples):
        partitions[index % number_of_clients].positive_examples.append(
            example
        )

    for index, example in enumerate(negative_examples):
        partitions[index % number_of_clients].negative_examples.append(
            example
        )

    return partitions


def _partition_non_iid(
    dataset: Dataset,
    number_of_clients: int,
    random_seed: int,
) -> list[DatasetPartition]:
    random_generator = random.Random(random_seed)

    positive_examples = list(dataset.positive_examples)
    negative_examples = list(dataset.negative_examples)

    random_generator.shuffle(positive_examples)
    random_generator.shuffle(negative_examples)

    partitions = [
        DatasetPartition(
            client_id=client_id,
            bias=dataset.bias,
        )
        for client_id in range(1, number_of_clients + 1)
    ]

    positive_weights = [
        index + 1
        for index in range(number_of_clients)
    ]

    negative_weights = list(reversed(positive_weights))

    positive_allocations = _weighted_allocation(
        total_items=len(positive_examples),
        weights=positive_weights,
    )

    negative_allocations = _weighted_allocation(
        total_items=len(negative_examples),
        weights=negative_weights,
    )

    positive_cursor = 0
    negative_cursor = 0

    for index, partition in enumerate(partitions):
        positive_count = positive_allocations[index]
        negative_count = negative_allocations[index]

        partition.positive_examples.extend(
            positive_examples[
                positive_cursor:
                positive_cursor + positive_count
            ]
        )

        partition.negative_examples.extend(
            negative_examples[
                negative_cursor:
                negative_cursor + negative_count
            ]
        )

        positive_cursor += positive_count
        negative_cursor += negative_count

    return partitions


def _weighted_allocation(
    total_items: int,
    weights: list[int],
) -> list[int]:
    if total_items == 0:
        return [0] * len(weights)

    weight_sum = sum(weights)

    raw_allocations = [
        total_items * weight / weight_sum
        for weight in weights
    ]

    allocations = [
        int(value)
        for value in raw_allocations
    ]

    remaining = total_items - sum(allocations)

    fractional_parts = sorted(
        enumerate(raw_allocations),
        key=lambda item: item[1] - int(item[1]),
        reverse=True,
    )

    for index, _ in fractional_parts[:remaining]:
        allocations[index] += 1

    return allocations


def _attach_background_knowledge(
    dataset: Dataset,
    partitions: list[DatasetPartition],
) -> None:
    shared_facts = [
        fact
        for fact in dataset.facts
        if fact.example_identifier is None
    ]

    for partition in partitions:
        example_identifiers = {
            _extract_numeric_identifier(example.identifier)
            for example in (
                partition.positive_examples
                + partition.negative_examples
            )
        }

        local_facts = [
            fact
            for fact in dataset.facts
            if (
                fact.example_identifier is not None
                and fact.example_identifier in example_identifiers
            )
        ]

        partition.facts = shared_facts + local_facts
        partition.rules = list(dataset.rules)


def _extract_numeric_identifier(
    example_identifier: str,
) -> str:
    start = example_identifier.find("(")
    end = example_identifier.rfind(")")

    if start == -1 or end == -1 or end <= start:
        return example_identifier

    return example_identifier[start + 1:end].strip()